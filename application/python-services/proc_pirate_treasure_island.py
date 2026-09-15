"""
proc_pirate_treasure_island.py — 190e procédural AuroraIA (54e qualité)
Île pirate trésor : galion + île tropicale + capitaine anatomie + équipage + trésor
Construction smooth (bevels + smooth shading + multi-axis animations + anatomie articulée hiérarchique)
"""
import bpy, bmesh, math, random, os

random.seed(0xB00714)  # BOOTY :)

# ============ HELPERS ============
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
              bpy.data.cameras, bpy.data.lights, bpy.data.collections):
        for x in list(c):
            try: c.remove(x)
            except: pass

def mat(name, base=(0.8,0.8,0.8,1.0), metallic=0.0, roughness=0.5,
        emission=None, emission_strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
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
    bm.to_mesh(me); bm.free()
    smooth_shade(me)
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

def smooth_sphere(name, r=1.0, segs=28, rings=18, loc=(0,0,0), parent=None, mat_=None, scale=(1,1,1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1,1,1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return make_obj(name, bm, loc, parent, mat_)

def smooth_cone(name, r1, r2, depth, segs=20, loc=(0,0,0), parent=None, mat_=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    return make_obj(name, bm, loc, parent, mat_)

def cyl(name, r, depth, segs=18, loc=(0,0,0), parent=None, mat_=None):
    return smooth_cone(name, r, r, depth, segs, loc, parent, mat_)

def empty(name, loc=(0,0,0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    if parent: e.parent = parent
    return e

# ============ SCENE ============
reset()
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 180
scene.render.fps = 30

# ============ MATERIALS ============
M_SKY = mat("sky", (0.6, 0.78, 0.95, 1.0), 0.0, 0.7, emission=(0.55, 0.75, 0.92), emission_strength=1.2)
M_SUN = mat("sun", (1.0, 0.96, 0.78, 1.0), 0.0, 0.3, emission=(1.0, 0.92, 0.65), emission_strength=15.0)
M_CLOUD = mat("cloud", (1.0, 1.0, 1.0, 1.0), 0.0, 0.6, emission=(0.95,0.95,1.0), emission_strength=0.8)
M_WATER = mat("water", (0.10, 0.35, 0.55, 1.0), 0.5, 0.10, emission=(0.15,0.45,0.65), emission_strength=0.6)
M_FOAM = mat("foam", (1.0, 1.0, 1.0, 1.0), 0.0, 0.4, emission=(0.95,0.98,1.0), emission_strength=1.5)
M_SAND = mat("sand", (0.92, 0.85, 0.65, 1.0), 0.0, 0.85, emission=(0.85,0.78,0.58), emission_strength=0.3)
M_ROCK = mat("rock", (0.50, 0.45, 0.40, 1.0), 0.0, 0.85)
M_CLIFF = mat("cliff", (0.55, 0.42, 0.32, 1.0), 0.0, 0.90)
M_GRASS = mat("grass", (0.30, 0.55, 0.25, 1.0), 0.0, 0.80)

M_WOOD_DARK = mat("wood_dark", (0.30, 0.20, 0.12, 1.0), 0.0, 0.75)
M_WOOD = mat("wood", (0.45, 0.30, 0.18, 1.0), 0.0, 0.70)
M_WOOD_LIGHT = mat("wood_light", (0.65, 0.45, 0.28, 1.0), 0.0, 0.65)
M_SAIL = mat("sail", (0.96, 0.93, 0.84, 1.0), 0.0, 0.55, emission=(0.85,0.82,0.75), emission_strength=0.3)
M_SAIL_TORN = mat("sail_torn", (0.85, 0.80, 0.70, 1.0), 0.0, 0.60, emission=(0.75,0.72,0.65), emission_strength=0.25)
M_ROPE = mat("rope", (0.60, 0.45, 0.30, 1.0), 0.0, 0.80)
M_METAL = mat("metal", (0.40, 0.40, 0.42, 1.0), 0.85, 0.30, emission=(0.30,0.30,0.32), emission_strength=0.2)
M_CANNON = mat("cannon", (0.15, 0.15, 0.18, 1.0), 0.85, 0.35, emission=(0.10,0.10,0.12), emission_strength=0.2)

M_JOLLY_BLACK = mat("jolly", (0.05, 0.05, 0.05, 1.0), 0.0, 0.7)
M_JOLLY_WHITE = mat("jolly_white", (0.98, 0.98, 0.95, 1.0), 0.0, 0.6, emission=(0.95,0.95,0.92), emission_strength=0.4)

M_GOLD = mat("gold", (1.0, 0.78, 0.25, 1.0), 0.95, 0.20, emission=(0.95,0.72,0.22), emission_strength=1.0)
M_GOLD_BRIGHT = mat("gold_bright", (1.0, 0.85, 0.35, 1.0), 0.95, 0.18, emission=(1.0,0.80,0.30), emission_strength=2.0)
M_CHEST = mat("chest", (0.40, 0.25, 0.15, 1.0), 0.0, 0.65)
M_CHEST_BAND = mat("chest_band", (0.55, 0.42, 0.20, 1.0), 0.85, 0.30, emission=(0.50,0.38,0.18), emission_strength=0.4)

# Pirate body parts
M_SKIN = mat("skin", (0.92, 0.75, 0.60, 1.0), 0.0, 0.6, emission=(0.85,0.70,0.55), emission_strength=0.15)
M_SKIN_DARK = mat("skin_dark", (0.65, 0.50, 0.38, 1.0), 0.0, 0.6, emission=(0.55,0.42,0.32), emission_strength=0.15)
M_COAT_RED = mat("coat_red", (0.65, 0.15, 0.12, 1.0), 0.0, 0.55, emission=(0.55,0.12,0.10), emission_strength=0.3)
M_COAT_BLUE = mat("coat_blue", (0.20, 0.30, 0.55, 1.0), 0.0, 0.55, emission=(0.15,0.25,0.48), emission_strength=0.3)
M_PANTS = mat("pants", (0.20, 0.18, 0.15, 1.0), 0.0, 0.75)
M_SHIRT_WHITE = mat("shirt_white", (0.92, 0.90, 0.82, 1.0), 0.0, 0.6, emission=(0.85,0.82,0.75), emission_strength=0.2)
M_SHIRT_STRIPE = mat("shirt_stripe", (0.85, 0.30, 0.30, 1.0), 0.0, 0.65, emission=(0.75,0.25,0.25), emission_strength=0.25)
M_HAT_BLACK = mat("hat_black", (0.08, 0.08, 0.08, 1.0), 0.0, 0.7)
M_BANDANA = mat("bandana", (0.75, 0.18, 0.15, 1.0), 0.0, 0.55, emission=(0.65,0.15,0.12), emission_strength=0.4)
M_BEARD = mat("beard", (0.10, 0.08, 0.05, 1.0), 0.0, 0.85)
M_HAIR = mat("hair", (0.20, 0.12, 0.08, 1.0), 0.0, 0.85)
M_BOOT = mat("boot", (0.12, 0.08, 0.05, 1.0), 0.0, 0.75)
M_HOOK = mat("hook", (0.85, 0.85, 0.88, 1.0), 0.95, 0.15, emission=(0.80,0.80,0.85), emission_strength=0.7)
M_SABER = mat("saber", (0.92, 0.93, 0.95, 1.0), 0.95, 0.10, emission=(0.85,0.88,0.92), emission_strength=0.8)

# Parrot
M_PARROT_RED = mat("parrot_red", (0.95, 0.15, 0.12, 1.0), 0.0, 0.55, emission=(0.90,0.12,0.10), emission_strength=0.7)
M_PARROT_YELLOW = mat("parrot_yellow", (1.0, 0.85, 0.20, 1.0), 0.0, 0.55, emission=(0.95,0.80,0.18), emission_strength=0.8)
M_PARROT_BLUE = mat("parrot_blue", (0.15, 0.35, 0.85, 1.0), 0.0, 0.55, emission=(0.12,0.30,0.80), emission_strength=0.7)
M_PARROT_BEAK = mat("parrot_beak", (0.25, 0.20, 0.15, 1.0), 0.0, 0.6)

# Palm
M_PALM_TRUNK = mat("palm_trunk", (0.42, 0.28, 0.18, 1.0), 0.0, 0.85)
M_PALM_LEAF = mat("palm_leaf", (0.18, 0.55, 0.22, 1.0), 0.0, 0.65, emission=(0.15,0.50,0.20), emission_strength=0.3)
M_COCONUT = mat("coconut", (0.30, 0.18, 0.10, 1.0), 0.0, 0.75)

# Seagulls
M_GULL = mat("gull", (0.95, 0.95, 0.92, 1.0), 0.0, 0.5, emission=(0.90,0.90,0.88), emission_strength=0.3)
M_GULL_DARK = mat("gull_dark", (0.30, 0.30, 0.33, 1.0), 0.0, 0.65)
M_GULL_BEAK = mat("gull_beak", (1.0, 0.65, 0.20, 1.0), 0.0, 0.55)

# Turtle
M_SHELL = mat("shell", (0.30, 0.42, 0.20, 1.0), 0.2, 0.65, emission=(0.25,0.35,0.18), emission_strength=0.3)
M_SHELL_DARK = mat("shell_dark", (0.20, 0.30, 0.15, 1.0), 0.2, 0.70)
M_TURTLE_SKIN = mat("turtle_skin", (0.50, 0.60, 0.35, 1.0), 0.0, 0.7)

# Map
M_PAPER = mat("paper", (0.92, 0.85, 0.65, 1.0), 0.0, 0.7, emission=(0.85,0.78,0.60), emission_strength=0.3)
M_INK = mat("ink", (0.30, 0.12, 0.05, 1.0), 0.0, 0.8)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky_dome", r=85.0, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.55))
sky.scale = (1,1,0.55)
sun = smooth_sphere("sun_disc", r=4.0, loc=(20, 30, 22), mat_=M_SUN)

clouds = []
for i in range(6):
    angle = (i / 6.0) * math.pi * 2
    cx = 25 * math.cos(angle) + random.uniform(-3, 3)
    cy = 28 + random.uniform(-3, 3)
    cz = 18 + random.uniform(-2, 4)
    cloud_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(4):
        smooth_sphere(f"cloud{i}_p{j}", r=random.uniform(2.0, 3.0),
                      loc=(random.uniform(-2, 2), random.uniform(-1, 1), random.uniform(-0.5, 0.5)),
                      parent=cloud_e, mat_=M_CLOUD)
    clouds.append(cloud_e)

# ============ OCEAN ============
ocean = beveled_cube("ocean", (60, 60, 0.5), bevel_offset=0.05, loc=(0, 0, -0.3), mat_=M_WATER)

# Wave foam ridges (8 strips)
foams = []
for i in range(8):
    angle = (i / 8.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(8, 20)
    fx, fy = rad*math.cos(angle), rad*math.sin(angle)
    foam = beveled_cube(f"foam{i}", (random.uniform(2.5, 4.5), 0.4, 0.05),
                       loc=(fx, fy, 0.1), mat_=M_FOAM)
    foam.rotation_euler = (0, 0, angle + math.pi/2)
    foam["_phase"] = random.uniform(0, math.pi*2)
    foams.append(foam)

# ============ ISLAND (tropical, center) ============
island_base = empty("island", loc=(0, 0, 0))
# Main sand mound (smooth dome)
sand_mound = smooth_sphere("sand_mound", r=10.0, segs=32, rings=18,
                            loc=(0, 0, -2.5), parent=island_base,
                            mat_=M_SAND, scale=(1.2, 1.1, 0.32))
# Grass patches on top
for i in range(5):
    a = (i/5.0) * math.pi * 2
    gx = math.cos(a) * 3.5 + random.uniform(-0.5, 0.5)
    gy = math.sin(a) * 3.5 + random.uniform(-0.5, 0.5)
    smooth_sphere(f"grass_p{i}", r=2.0, loc=(gx, gy, 0.5), parent=island_base,
                  mat_=M_GRASS, scale=(1, 1, 0.2))

# Rocks scattered
for i in range(8):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 9)
    rx, ry = rad*math.cos(a), rad*math.sin(a)
    rock = smooth_sphere(f"rock{i}", r=random.uniform(0.5, 1.2),
                       loc=(rx, ry, 0.1), parent=island_base, mat_=M_ROCK,
                       scale=(random.uniform(0.8,1.3), random.uniform(0.8,1.3), random.uniform(0.6,1.0)))
    rock.rotation_euler = (0, 0, random.uniform(0, math.pi*2))

# ============ CLIFF (back of island, with cascade) ============
cliff_base = empty("cliff", loc=(0, 8, 0))
# Cliff main body
beveled_cube("cliff_body", (8, 4, 8), bevel_offset=0.15, loc=(0, 0, 4), parent=cliff_base, mat_=M_CLIFF)
# Cliff secondary rocks
beveled_cube("cliff_top1", (5, 3, 1.5), loc=(-1.5, -0.5, 8.5), parent=cliff_base, mat_=M_CLIFF)
beveled_cube("cliff_top2", (4, 2.5, 1.0), loc=(2, 0.5, 9.0), parent=cliff_base, mat_=M_CLIFF)
# Grass on cliff top
smooth_sphere("cliff_grass", r=2.0, loc=(0, 0, 9.5), parent=cliff_base, mat_=M_GRASS, scale=(2.5, 1.5, 0.25))

# Cascade (water flowing down cliff - 6 segments)
cascade_segs = []
cascade_base = empty("cascade", loc=(0, 6.5, 0), parent=cliff_base)
for i in range(8):
    z = 7.5 - i * 0.95
    seg = beveled_cube(f"cascade{i}", (1.2, 0.3, 1.1), bevel_offset=0.08,
                       loc=(0, 0, z), parent=cascade_base, mat_=M_WATER)
    seg["_base_z"] = z
    cascade_segs.append(seg)
# Cascade spray pool at bottom
smooth_sphere("cascade_pool", r=2.0, loc=(0, 0.5, 0.05),
              parent=cliff_base, mat_=M_WATER, scale=(1.2, 1.0, 0.1))
# Foam at base of cascade
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    smooth_sphere(f"cascade_foam{i}", r=0.35, loc=(0.7*math.cos(a), 0.5+0.7*math.sin(a), 0.15),
                  parent=cliff_base, mat_=M_FOAM)

# ============ PALM TREES (6 palms) ============
def make_palm(name, loc, scale=1.0, lean=0):
    base = empty(name, loc)
    # Trunk 6 segments curved
    parent = base
    h_per = 1.1 * scale
    for i in range(6):
        r1 = (0.30 - i*0.025) * scale
        r2 = (0.27 - i*0.025) * scale
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=h_per, segs=14,
                          loc=(0, 0, (i+0.5)*h_per), parent=base, mat_=M_PALM_TRUNK)
        # Slight curve
        bend = lean * (i / 6.0)
        seg.rotation_euler = (math.radians(bend*5), math.radians(bend*3), 0)
    # Top: 7 fronds radiating
    top_z = 6 * h_per
    for i in range(7):
        a = (i / 7.0) * math.pi * 2
        frond = empty(f"{name}_f_e{i}", (0, 0, top_z), parent=base)
        frond.rotation_euler = (math.radians(-65), 0, a)
        # Frond made of 4 segments
        for j in range(4):
            seg = beveled_cube(f"{name}_f{i}_{j}", (0.20*scale, 1.0*scale, 0.05*scale),
                               loc=(0, (j+0.5)*1.0*scale, 0), parent=frond, mat_=M_PALM_LEAF)
            # taper
            seg.scale = (1 - j*0.15, 1, 1)
            # slight downward curve
            seg.rotation_euler = (math.radians(j*4), 0, 0)
        frond["_phase"] = random.uniform(0, math.pi*2)
    # 2 coconuts at top base
    for i in range(2):
        smooth_sphere(f"{name}_coco{i}", r=0.18*scale,
                      loc=(0.25*scale*(1 if i else -1), 0, top_z + 0.1),
                      parent=base, mat_=M_COCONUT)
    return base

palms = []
palm_positions = [
    (-6, -3, 0.5, 1.1, 1),
    (5.5, -2.5, 0.5, 1.0, -1),
    (-4, 2, 0.5, 0.95, 0),
    (4, 3, 0.5, 1.05, 1),
    (-2, -5, 0.5, 0.9, 0),
    (2, -6, 0.5, 1.0, -1),
]
for i, (x, y, z, s, l) in enumerate(palm_positions):
    p = make_palm(f"palm{i}", (x, y, z), scale=s, lean=l)
    palms.append(p)

# ============ TREASURE CHEST (open, gold coins) ============
chest_base = empty("chest", loc=(-1.5, -1.5, 0.6))
chest_base.rotation_euler = (0, 0, math.radians(20))
# Body
beveled_cube("chest_body", (1.4, 0.9, 0.85), bevel_offset=0.06,
             loc=(0, 0, 0), parent=chest_base, mat_=M_CHEST)
# Bands gold
for z in (0.30, -0.30):
    beveled_cube(f"chest_band{z}", (1.45, 0.95, 0.06), loc=(0, 0, z),
                 parent=chest_base, mat_=M_CHEST_BAND)
# Lid - tilted open
lid_e = empty("chest_lid_e", (0, -0.45, 0.42), parent=chest_base)
lid_e.rotation_euler = (math.radians(-65), 0, 0)
# Lid is half-cylinder approximation (rounded top via flat top + 2 ramps)
beveled_cube("chest_lid_top", (1.4, 0.9, 0.35), bevel_offset=0.08,
             loc=(0, 0.05, 0.10), parent=lid_e, mat_=M_CHEST)
beveled_cube("chest_lid_band", (1.45, 0.95, 0.06), loc=(0, 0.05, 0.30),
             parent=lid_e, mat_=M_CHEST_BAND)
# Lock
smooth_sphere("chest_lock", r=0.12, loc=(0, -0.48, 0), parent=chest_base, mat_=M_GOLD_BRIGHT)
# Gold coins inside (mound) + scattered around
for i in range(40):
    if i < 25:
        # Inside chest
        x = random.uniform(-0.55, 0.55)
        y = random.uniform(-0.35, 0.35)
        z = 0.40 + random.uniform(-0.05, 0.15)
        coin = cyl(f"coin{i}", r=0.10, depth=0.025, segs=14,
                   loc=(x, y, z), parent=chest_base, mat_=M_GOLD_BRIGHT)
    else:
        # Scattered outside
        a = random.uniform(0, math.pi*2)
        rad = random.uniform(0.9, 2.2)
        x = rad*math.cos(a)
        y = rad*math.sin(a) - 0.5
        z = 0.05
        coin = cyl(f"coin{i}", r=0.10, depth=0.025, segs=14,
                   loc=(x, y, z), parent=chest_base, mat_=M_GOLD_BRIGHT)
    coin.rotation_euler = (random.uniform(-0.3, 0.3),
                           random.uniform(-0.3, 0.3),
                           random.uniform(0, math.pi*2))
    coin["_phase"] = random.uniform(0, math.pi*2)
# Pearls + gems on top
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    smooth_sphere(f"pearl{i}", r=0.06, loc=(0.35*math.cos(a), 0.20*math.sin(a), 0.55),
                  parent=chest_base, mat_=M_GULL)
gem_colors = [M_PARROT_RED, M_PARROT_BLUE, M_PARROT_YELLOW]
for i in range(3):
    gem = smooth_sphere(f"gem{i}", r=0.10, loc=((i-1)*0.20, 0.10, 0.58),
                       parent=chest_base, mat_=gem_colors[i],
                       scale=(1, 1, 0.7))

# ============ TREASURE MAP (unrolled on sand) ============
map_base = empty("map", loc=(2.0, 1.0, 0.05))
map_base.rotation_euler = (0, 0, math.radians(-30))
# Paper sheet (slightly curled)
beveled_cube("map_sheet", (1.2, 0.9, 0.02), bevel_offset=0.02,
             loc=(0, 0, 0.01), parent=map_base, mat_=M_PAPER)
# Rolled edges (right side curled up)
roll_r = cyl("map_roll_r", r=0.05, depth=0.85, segs=12,
              loc=(0.6, 0, 0.05), parent=map_base, mat_=M_PAPER)
roll_r.rotation_euler = (math.radians(90), 0, 0)
# X mark
for i, (dx, dy) in enumerate([(-0.05, -0.05), (0.05, 0.05), (-0.05, 0.05), (0.05, -0.05)]):
    beveled_cube(f"map_x{i}", (0.20, 0.04, 0.005),
                 loc=(-0.15 + dx*1, -0.2 + dy*1, 0.025),
                 parent=map_base, mat_=M_INK)
# Path lines
for i in range(4):
    seg = beveled_cube(f"map_path{i}", (0.04, 0.18, 0.005),
                       loc=(-0.4 + i*0.18, 0.1 - (i%2)*0.05, 0.025),
                       parent=map_base, mat_=M_INK)
    seg.rotation_euler = (0, 0, math.radians(20 + i*15))

# ============ PIRATE CAPTAIN (anatomie complète) ============
def make_pirate_captain(name, loc):
    """Captain: hat bicorne + bandeau eye + barbe + beard + arms (1 hook) + saber + parrot on shoulder"""
    base = empty(name, loc)
    # Legs (boots wide)
    for side_idx, side in enumerate((-1, 1)):
        leg_e = empty(f"{name}_leg_e{side_idx}", (side*0.18, 0, 0.95), parent=base)
        # Thigh
        beveled_cube(f"{name}_thigh_{side_idx}", (0.22, 0.22, 0.85),
                     loc=(0, 0, -0.4), parent=leg_e, mat_=M_PANTS)
        # Calf
        beveled_cube(f"{name}_calf_{side_idx}", (0.20, 0.20, 0.75),
                     loc=(0, 0, -1.15), parent=leg_e, mat_=M_PANTS)
        # Boot (tall pirate boot folded down)
        beveled_cube(f"{name}_boot_{side_idx}", (0.28, 0.32, 0.50),
                     bevel_offset=0.05,
                     loc=(0, 0.05, -1.75), parent=leg_e, mat_=M_BOOT)
        # Boot folded cuff top
        beveled_cube(f"{name}_boot_cuff_{side_idx}", (0.32, 0.36, 0.18),
                     loc=(0, 0.04, -1.50), parent=leg_e, mat_=M_BOOT)
    # Torso (long pirate coat red)
    beveled_cube(f"{name}_torso", (0.78, 0.55, 1.10),
                 bevel_offset=0.07, loc=(0, 0, 1.95), parent=base, mat_=M_COAT_RED)
    # Coat tails (flared bottom 4 panels)
    for i in range(4):
        panel = beveled_cube(f"{name}_coat_tail{i}", (0.22, 0.10, 0.60),
                             loc=((i-1.5)*0.20, 0, 1.05), parent=base, mat_=M_COAT_RED)
        panel.rotation_euler = (0, math.radians((i-1.5)*5), 0)
    # Coat lapels (gold trim)
    for side_idx, side in enumerate((-1, 1)):
        beveled_cube(f"{name}_lapel_{side_idx}", (0.10, 0.05, 0.85),
                     loc=(side*0.32, -0.30, 2.0), parent=base, mat_=M_GOLD)
    # Belt + buckle gold
    beveled_cube(f"{name}_belt", (0.85, 0.60, 0.15), loc=(0, 0, 1.40),
                 parent=base, mat_=M_BOOT)
    beveled_cube(f"{name}_buckle", (0.20, 0.10, 0.20), loc=(0, -0.32, 1.40),
                 parent=base, mat_=M_GOLD_BRIGHT)
    # Shirt visible at neck (white)
    beveled_cube(f"{name}_shirt", (0.40, 0.20, 0.30), loc=(0, -0.25, 2.45),
                 parent=base, mat_=M_SHIRT_WHITE)
    # Cravat/jabot (ruffle)
    smooth_sphere(f"{name}_cravat", r=0.18, loc=(0, -0.35, 2.50),
                  parent=base, mat_=M_SHIRT_WHITE, scale=(1, 0.6, 1.3))
    # Neck
    cyl(f"{name}_neck", r=0.16, depth=0.25, segs=14, loc=(0, 0, 2.65),
        parent=base, mat_=M_SKIN_DARK)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 2.90), parent=base)
    smooth_sphere(f"{name}_head", r=0.32, segs=24, rings=16,
                  loc=(0, 0, 0), parent=head_e, mat_=M_SKIN_DARK)
    # Eye patch (black) on right eye
    eye_patch = beveled_cube(f"{name}_patch", (0.18, 0.05, 0.14), bevel_offset=0.02,
                              loc=(0.12, -0.27, 0.05), parent=head_e, mat_=M_JOLLY_BLACK)
    # Strap (around head)
    cyl(f"{name}_strap", r=0.34, depth=0.04, segs=24,
        loc=(0, 0, 0.05), parent=head_e, mat_=M_JOLLY_BLACK)
    # Left eye (open, slight glow)
    smooth_sphere(f"{name}_eye_L", r=0.05, loc=(-0.12, -0.27, 0.05),
                  parent=head_e, mat_=M_SHIRT_WHITE)
    smooth_sphere(f"{name}_pupil_L", r=0.025, loc=(-0.12, -0.31, 0.05),
                  parent=head_e, mat_=M_JOLLY_BLACK)
    # Nose
    smooth_sphere(f"{name}_nose", r=0.07, loc=(0, -0.32, -0.03),
                  parent=head_e, mat_=M_SKIN_DARK, scale=(1, 1.3, 1))
    # Mouth/teeth
    beveled_cube(f"{name}_mouth", (0.14, 0.04, 0.05), loc=(0, -0.30, -0.15),
                 parent=head_e, mat_=M_JOLLY_BLACK)
    # BEARD (long, full)
    for i in range(5):
        bw = 0.18 - i*0.02
        beard_seg = beveled_cube(f"{name}_beard{i}", (bw, 0.08, 0.20),
                                  loc=(0, -0.28, -0.32 - i*0.18),
                                  parent=head_e, mat_=M_BEARD)
        beard_seg.rotation_euler = (math.radians(5 + i*3), 0, 0)
    # Sideburns
    for side_idx, side in enumerate((-1, 1)):
        smooth_sphere(f"{name}_burns_{side_idx}", r=0.12, loc=(side*0.28, -0.05, -0.15),
                      parent=head_e, mat_=M_BEARD, scale=(0.6, 0.7, 1.2))
    # Hair (back)
    smooth_sphere(f"{name}_hair_back", r=0.30, loc=(0, 0.15, -0.08),
                  parent=head_e, mat_=M_HAIR, scale=(1.05, 0.6, 1.1))
    # BICORNE HAT (large pirate hat)
    hat_e = empty(f"{name}_hat_e", (0, 0, 0.35), parent=head_e)
    # Hat crown (low dome)
    smooth_sphere(f"{name}_hat_crown", r=0.36, loc=(0, 0, 0),
                  parent=hat_e, mat_=M_HAT_BLACK, scale=(1, 1, 0.55))
    # Bicorne wings (two pointed extensions left/right)
    for side_idx, side in enumerate((-1, 1)):
        wing = beveled_cube(f"{name}_hat_wing{side_idx}", (0.6, 0.20, 0.18),
                            bevel_offset=0.05,
                            loc=(side*0.45, 0, 0.05), parent=hat_e, mat_=M_HAT_BLACK)
        wing.rotation_euler = (0, math.radians(side*15), 0)
    # Skull insignia (white on front)
    skull = smooth_sphere(f"{name}_hat_skull", r=0.10, loc=(0, -0.30, 0.05),
                          parent=hat_e, mat_=M_JOLLY_WHITE, scale=(1, 0.3, 1))
    # Hat feather (gold)
    feather = beveled_cube(f"{name}_hat_feather", (0.06, 0.05, 0.55),
                           loc=(-0.05, -0.20, 0.40), parent=hat_e, mat_=M_GOLD)
    feather.rotation_euler = (math.radians(-15), 0, math.radians(-25))

    # ARMS
    # Right arm (with HOOK)
    r_shoulder = empty(f"{name}_r_sh", (0.50, 0, 2.40), parent=base)
    r_shoulder.rotation_euler = (math.radians(-20), 0, math.radians(-20))
    beveled_cube(f"{name}_r_upper", (0.20, 0.20, 0.60), loc=(0, 0, -0.30),
                 parent=r_shoulder, mat_=M_COAT_RED)
    r_elbow = empty(f"{name}_r_el", (0, 0, -0.62), parent=r_shoulder)
    r_elbow.rotation_euler = (math.radians(25), 0, 0)
    beveled_cube(f"{name}_r_forearm", (0.18, 0.18, 0.55), loc=(0, 0, -0.28),
                 parent=r_elbow, mat_=M_SHIRT_WHITE)
    # HOOK (curved metal)
    hook_e = empty(f"{name}_hook_e", (0, 0, -0.60), parent=r_elbow)
    # Hook stem
    cyl(f"{name}_hook_stem", r=0.04, depth=0.20, segs=10,
        loc=(0, 0, -0.10), parent=hook_e, mat_=M_HOOK)
    # Hook curve (2 segments curving)
    h_curve1 = beveled_cube(f"{name}_hook_c1", (0.05, 0.05, 0.18),
                            loc=(0, 0.03, -0.30), parent=hook_e, mat_=M_HOOK)
    h_curve1.rotation_euler = (math.radians(35), 0, 0)
    h_curve2 = beveled_cube(f"{name}_hook_c2", (0.05, 0.05, 0.18),
                            loc=(0, 0.13, -0.45), parent=hook_e, mat_=M_HOOK)
    h_curve2.rotation_euler = (math.radians(80), 0, 0)
    # Hook tip
    smooth_cone(f"{name}_hook_tip", r1=0.04, r2=0.005, depth=0.10, segs=8,
                loc=(0, 0.22, -0.43), parent=hook_e, mat_=M_HOOK)

    # Left arm (with saber raised)
    l_shoulder = empty(f"{name}_l_sh", (-0.50, 0, 2.40), parent=base)
    l_shoulder.rotation_euler = (math.radians(-110), 0, math.radians(15))
    beveled_cube(f"{name}_l_upper", (0.20, 0.20, 0.60), loc=(0, 0, -0.30),
                 parent=l_shoulder, mat_=M_COAT_RED)
    l_elbow = empty(f"{name}_l_el", (0, 0, -0.62), parent=l_shoulder)
    l_elbow.rotation_euler = (math.radians(30), 0, 0)
    beveled_cube(f"{name}_l_forearm", (0.18, 0.18, 0.55), loc=(0, 0, -0.28),
                 parent=l_elbow, mat_=M_SHIRT_WHITE)
    # Left hand
    l_hand = empty(f"{name}_l_hand", (0, 0, -0.60), parent=l_elbow)
    smooth_sphere(f"{name}_l_hand_g", r=0.10, loc=(0, 0, 0),
                  parent=l_hand, mat_=M_SKIN_DARK)
    # SABER (cutlass)
    saber_e = empty(f"{name}_saber_e", (0, 0, -0.05), parent=l_hand)
    # Handle
    cyl(f"{name}_saber_handle", r=0.04, depth=0.25, segs=10,
        loc=(0, 0, -0.10), parent=saber_e, mat_=M_HAT_BLACK)
    # Guard (curved D-guard)
    guard = cyl(f"{name}_saber_guard", r=0.13, depth=0.04, segs=14,
                loc=(0, 0, -0.05), parent=saber_e, mat_=M_GOLD_BRIGHT)
    guard.rotation_euler = (math.radians(90), 0, 0)
    # Blade (curved cutlass - 3 segments)
    blade_e = empty(f"{name}_blade_e", (0, 0, 0), parent=saber_e)
    for i in range(3):
        bseg = beveled_cube(f"{name}_blade_s{i}", (0.04, 0.04, 0.35),
                           bevel_offset=0.005,
                           loc=(0, -i*0.05, 0.10 + i*0.32), parent=blade_e, mat_=M_SABER)
        bseg.rotation_euler = (math.radians(i*8), 0, 0)
    smooth_cone(f"{name}_blade_tip", r1=0.03, r2=0.005, depth=0.15, segs=10,
                loc=(0, -0.14, 1.15), parent=blade_e, mat_=M_SABER)

    return {"root": base, "head_e": head_e, "l_shoulder": l_shoulder,
            "r_shoulder": r_shoulder, "saber": saber_e, "hat_e": hat_e}

captain = make_pirate_captain("captain", (0.5, 0.5, 0.6))
captain["root"].rotation_euler = (0, 0, math.radians(-40))

# ============ PARROT on captain shoulder ============
parrot_e = empty("parrot", (0.85, -0.1, 2.65), parent=captain["root"])
# Body
smooth_sphere("parrot_body", r=0.22, loc=(0, 0, 0), parent=parrot_e,
              mat_=M_PARROT_RED, scale=(1.0, 1.5, 1.0))
# Yellow belly
smooth_sphere("parrot_belly", r=0.18, loc=(0, -0.1, 0), parent=parrot_e,
              mat_=M_PARROT_YELLOW, scale=(0.8, 0.7, 0.8))
# Head
parrot_head = empty("parrot_head", (0, -0.30, 0.18), parent=parrot_e)
smooth_sphere("parrot_h", r=0.16, loc=(0, 0, 0), parent=parrot_head, mat_=M_PARROT_RED)
# Beak (large curved)
beak_top = smooth_cone("parrot_beak_t", r1=0.08, r2=0.02, depth=0.18, segs=12,
                       loc=(0, -0.12, -0.05), parent=parrot_head, mat_=M_PARROT_BEAK)
beak_top.rotation_euler = (math.radians(90), 0, 0)
# Eye
smooth_sphere("parrot_eye", r=0.04, loc=(0.08, -0.10, 0.05), parent=parrot_head,
              mat_=M_SHIRT_WHITE)
smooth_sphere("parrot_pupil", r=0.02, loc=(0.10, -0.12, 0.05), parent=parrot_head,
              mat_=M_JOLLY_BLACK)
# Wings (folded)
parrot_wings = []
for side_idx, side in enumerate((-1, 1)):
    w_e = empty(f"parrot_wing_e{side_idx}", (side*0.18, 0, 0.08), parent=parrot_e)
    beveled_cube(f"parrot_wing{side_idx}", (0.10, 0.40, 0.04), bevel_offset=0.02,
                 loc=(0, 0, 0), parent=w_e, mat_=M_PARROT_BLUE)
    parrot_wings.append(w_e)
# Tail feathers
for i in range(3):
    color = [M_PARROT_RED, M_PARROT_YELLOW, M_PARROT_BLUE][i]
    beveled_cube(f"parrot_tail{i}", (0.04, 0.30, 0.03),
                 loc=((i-1)*0.05, 0.30, -0.05), parent=parrot_e, mat_=color)
# Feet
for side_idx, side in enumerate((-1, 1)):
    cyl(f"parrot_foot{side_idx}", r=0.03, depth=0.12, segs=8,
        loc=(side*0.06, 0, -0.20), parent=parrot_e, mat_=M_PARROT_BEAK)

# ============ 5 PIRATE CREW (simpler anatomie, varied) ============
def make_crew(name, loc, coat_color, skin_color, hat_type="bandana"):
    base = empty(name, loc)
    # Legs
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"{name}_leg_{side_idx}", r=0.13, depth=0.85, segs=12,
            loc=(side*0.15, 0, 0.45), parent=base, mat_=M_PANTS)
        beveled_cube(f"{name}_boot_{side_idx}", (0.20, 0.28, 0.30),
                     loc=(side*0.15, 0.05, 0.10), parent=base, mat_=M_BOOT)
    # Torso
    beveled_cube(f"{name}_torso", (0.55, 0.32, 0.80),
                 loc=(0, 0, 1.30), parent=base, mat_=coat_color)
    # Belt
    beveled_cube(f"{name}_belt", (0.60, 0.36, 0.08), loc=(0, 0, 0.95),
                 parent=base, mat_=M_BOOT)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, 1.90), parent=base)
    smooth_sphere(f"{name}_head", r=0.22, segs=20, rings=14,
                  loc=(0, 0, 0), parent=head_e, mat_=skin_color)
    # Eyes
    for side_idx, side in enumerate((-1, 1)):
        smooth_sphere(f"{name}_eye_{side_idx}", r=0.04,
                      loc=(side*0.07, -0.19, 0.03), parent=head_e, mat_=M_SHIRT_WHITE)
        smooth_sphere(f"{name}_pup_{side_idx}", r=0.02,
                      loc=(side*0.07, -0.22, 0.03), parent=head_e, mat_=M_JOLLY_BLACK)
    # Mouth
    beveled_cube(f"{name}_mouth", (0.10, 0.03, 0.03), loc=(0, -0.21, -0.10),
                 parent=head_e, mat_=M_JOLLY_BLACK)
    # Hat
    if hat_type == "bandana":
        smooth_sphere(f"{name}_bandana", r=0.24, loc=(0, 0, 0.10),
                      parent=head_e, mat_=M_BANDANA, scale=(1, 1, 0.5))
        # bandana tail
        beveled_cube(f"{name}_b_tail", (0.06, 0.18, 0.04),
                     loc=(0.18, 0.05, 0.05), parent=head_e, mat_=M_BANDANA)
    else:  # tricorne
        smooth_sphere(f"{name}_hat_c", r=0.26, loc=(0, 0, 0.15),
                      parent=head_e, mat_=M_HAT_BLACK, scale=(1, 1, 0.45))
        for i in range(3):
            a = (i / 3.0) * math.pi * 2 - math.pi/2
            tri = beveled_cube(f"{name}_h_tri{i}", (0.30, 0.10, 0.06),
                              loc=(0.30*math.cos(a), 0.30*math.sin(a), 0.10),
                              parent=head_e, mat_=M_HAT_BLACK)
            tri.rotation_euler = (0, 0, a + math.pi/2)
    # Arms (one raised cheering, one down)
    for side_idx, side in enumerate((-1, 1)):
        sh_e = empty(f"{name}_sh{side_idx}", (side*0.32, 0, 1.65), parent=base)
        raise_arm = (side == 1)  # right arm up
        if raise_arm:
            sh_e.rotation_euler = (math.radians(-150), 0, 0)
        else:
            sh_e.rotation_euler = (math.radians(-15), 0, math.radians(side*-10))
        cyl(f"{name}_upper_{side_idx}", r=0.10, depth=0.50, segs=10,
            loc=(0, 0, -0.25), parent=sh_e, mat_=coat_color)
        el_e = empty(f"{name}_el{side_idx}", (0, 0, -0.52), parent=sh_e)
        cyl(f"{name}_fa_{side_idx}", r=0.08, depth=0.45, segs=10,
            loc=(0, 0, -0.22), parent=el_e, mat_=M_SHIRT_WHITE)
        # Fist
        smooth_sphere(f"{name}_fist_{side_idx}", r=0.10,
                      loc=(0, 0, -0.50), parent=el_e, mat_=skin_color)
    return {"root": base, "head_e": head_e}

crew_specs = [
    ("crew0", (-3.5, -1.0, 0.5), M_COAT_BLUE, M_SKIN, "bandana"),
    ("crew1", (3.0, -1.5, 0.5), M_SHIRT_STRIPE, M_SKIN_DARK, "tricorne"),
    ("crew2", (-2.5, 1.5, 0.5), M_COAT_RED, M_SKIN, "bandana"),
    ("crew3", (3.5, 2.0, 0.5), M_SHIRT_WHITE, M_SKIN_DARK, "tricorne"),
    ("crew4", (-3.8, 2.5, 0.5), M_SHIRT_STRIPE, M_SKIN, "bandana"),
]
crews = []
for spec in crew_specs:
    c = make_crew(*spec)
    c["root"].rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    crews.append(c)

# ============ GALION PIRATE (anchored offshore) ============
ship_base = empty("ship", loc=(-14, -10, 0.5))
ship_base.rotation_euler = (0, 0, math.radians(-25))

# Hull (3-tier: bottom + main + bulwarks)
beveled_cube("hull_bot", (5.5, 1.6, 1.0), bevel_offset=0.12,
             loc=(0, 0, 0), parent=ship_base, mat_=M_WOOD_DARK)
beveled_cube("hull_main", (5.2, 1.4, 0.8), bevel_offset=0.10,
             loc=(0, 0, 0.85), parent=ship_base, mat_=M_WOOD)
# Bow (front pointed - using a tilted beveled cube)
bow = beveled_cube("bow", (1.5, 1.3, 1.2), bevel_offset=0.10,
                   loc=(3.0, 0, 0.6), parent=ship_base, mat_=M_WOOD_DARK)
bow.rotation_euler = (0, math.radians(15), 0)
# Stern (raised aft castle)
beveled_cube("stern", (1.8, 1.5, 1.5), bevel_offset=0.10,
             loc=(-2.6, 0, 1.5), parent=ship_base, mat_=M_WOOD)
# Bowsprit
bowsprit = cyl("bowsprit", r=0.10, depth=1.8, segs=10,
                loc=(3.9, 0, 1.2), parent=ship_base, mat_=M_WOOD)
bowsprit.rotation_euler = (0, math.radians(-25), 0)

# Gold trim on hull
beveled_cube("hull_trim", (5.3, 1.5, 0.10), loc=(0, 0, 0.40),
             parent=ship_base, mat_=M_GOLD)

# 6 Hull windows (gold émissif)
for i in range(6):
    for side in (-1, 1):
        smooth_sphere(f"window_{i}_{side}", r=0.10,
                     loc=(-2 + i*0.7, side*0.7, 0.45), parent=ship_base,
                     mat_=M_GOLD_BRIGHT, scale=(0.8, 0.3, 0.8))

# 3 MASTS
masts = []
mast_positions = [(2.0, "fore"), (0.0, "main"), (-1.8, "mizzen")]
for mx, name in mast_positions:
    m_e = empty(f"mast_{name}", (mx, 0, 1.5), parent=ship_base)
    # Mast pole
    cyl(f"mast_pole_{name}", r=0.12, depth=4.5, segs=12,
        loc=(0, 0, 2.25), parent=m_e, mat_=M_WOOD)
    # Top cap
    smooth_sphere(f"mast_top_{name}", r=0.16, loc=(0, 0, 4.5),
                  parent=m_e, mat_=M_GOLD)
    # 2 yard arms (horizontal) with sails
    for j, yz in enumerate([1.2, 2.8]):
        yard = beveled_cube(f"yard_{name}_{j}", (0.06, 2.8, 0.06),
                           loc=(0, 0, yz), parent=m_e, mat_=M_WOOD_DARK)
        # SAIL
        sail_mat = M_SAIL_TORN if random.random() < 0.3 else M_SAIL
        sail = beveled_cube(f"sail_{name}_{j}", (0.06, 2.6, 1.3), bevel_offset=0.03,
                           loc=(0, 0, yz - 0.65), parent=m_e, mat_=sail_mat)
        # Bulge sails forward (front-back deflection)
        sail.scale = (1.5, 1, 1)
        sail["_phase"] = random.uniform(0, math.pi*2)
    # Crow's nest at top of main mast
    if name == "main":
        cyl(f"nest_{name}", r=0.45, depth=0.4, segs=20,
            loc=(0, 0, 3.7), parent=m_e, mat_=M_WOOD_DARK)
        # nest rail
        cyl(f"nest_rail_{name}", r=0.45, depth=0.05, segs=20,
            loc=(0, 0, 3.95), parent=m_e, mat_=M_WOOD)
    masts.append(m_e)

# JOLLY ROGER FLAG (on mizzen top)
flag_e = empty("flag", (0, 0, 4.3), parent=masts[2])
# Flag cloth (rectangular)
flag = beveled_cube("flag_cloth", (0.04, 1.4, 0.85), bevel_offset=0.02,
                    loc=(0, 0.7, 0), parent=flag_e, mat_=M_JOLLY_BLACK)
# Skull on flag (white)
smooth_sphere("flag_skull", r=0.18, loc=(0.05, 0.7, 0.15),
              parent=flag_e, mat_=M_JOLLY_WHITE, scale=(1, 1.2, 1.2))
# Crossed bones
for i in (-1, 1):
    bone = beveled_cube(f"flag_bone{i}", (0.025, 0.6, 0.04),
                        loc=(0.06, 0.7 + i*0.05, -0.15), parent=flag_e, mat_=M_JOLLY_WHITE)
    bone.rotation_euler = (0, math.radians(i*30), 0)

# 6 CANNONS (3 each side)
for side_idx, side in enumerate((-1, 1)):
    for i in range(3):
        cx = -1.5 + i * 1.5
        cannon_e = empty(f"cannon_e_{side_idx}_{i}", (cx, side*0.85, 1.0), parent=ship_base)
        cannon_e.rotation_euler = (0, 0, math.radians(side*90))
        cyl(f"cannon_barrel_{side_idx}_{i}", r=0.10, depth=0.7, segs=12,
            loc=(0, 0, -0.35), parent=cannon_e, mat_=M_CANNON)
        # Carriage
        beveled_cube(f"cannon_carr_{side_idx}_{i}", (0.20, 0.20, 0.15),
                     loc=(0, 0, -0.15), parent=cannon_e, mat_=M_WOOD_DARK)
        # 2 wheels
        for w_idx, w_side in enumerate((-1, 1)):
            wheel = cyl(f"cannon_wheel_{side_idx}_{i}_{w_idx}", r=0.07, depth=0.04, segs=12,
                       loc=(w_side*0.10, 0.10, -0.18), parent=cannon_e, mat_=M_WOOD)
            wheel.rotation_euler = (math.radians(90), 0, 0)

# Rigging ropes (8 ropes from masts to deck)
for i, m_e in enumerate(masts):
    for side in (-1, 1):
        for j in range(2):
            rope = cyl(f"rigging_{i}_{side}_{j}", r=0.015, depth=4.5, segs=6,
                      loc=(0, side*(0.4 + j*0.3), 2.0), parent=m_e, mat_=M_ROPE)
            rope.rotation_euler = (math.radians(side*15 + j*8), 0, 0)

# ============ SEA TURTLE (on sand) ============
turtle_base = empty("turtle", loc=(3.5, -3.5, 0.18))
turtle_base.rotation_euler = (0, 0, math.radians(45))
# Shell
shell = smooth_sphere("turtle_shell", r=0.55, loc=(0, 0, 0.10),
                      parent=turtle_base, mat_=M_SHELL,
                      scale=(1.0, 1.3, 0.45))
# Shell pattern dots
for i in range(6):
    a = (i / 6.0) * math.pi * 2
    smooth_sphere(f"shell_dot{i}", r=0.10, loc=(0.30*math.cos(a), 0.40*math.sin(a), 0.30),
                  parent=turtle_base, mat_=M_SHELL_DARK, scale=(1, 1, 0.3))
# Head
turtle_head = smooth_sphere("turtle_head", r=0.15, loc=(0, 0.65, 0.08),
                             parent=turtle_base, mat_=M_TURTLE_SKIN,
                             scale=(0.9, 1.1, 0.8))
# 4 flippers
for side_idx, side in enumerate((-1, 1)):
    for f_idx, f_pos in enumerate((0.30, -0.30)):
        flipper = beveled_cube(f"flipper_{side_idx}_{f_idx}", (0.20, 0.35, 0.08),
                              loc=(side*0.45, f_pos, 0.05), parent=turtle_base, mat_=M_TURTLE_SKIN)
        flipper.rotation_euler = (0, 0, math.radians(side*30))
        flipper["_side"] = side
# Tail
smooth_cone("turtle_tail", r1=0.08, r2=0.02, depth=0.20, segs=10,
            loc=(0, -0.65, 0.05), parent=turtle_base, mat_=M_TURTLE_SKIN)

# ============ 50 SEAGULLS (flying) ============
seagulls = []
for i in range(50):
    a = (i / 50.0) * math.pi * 2 + random.uniform(-0.2, 0.2)
    rad = random.uniform(15, 25)
    cx = rad * math.cos(a)
    cy = rad * math.sin(a)
    cz = random.uniform(8, 18)
    gull_e = empty(f"gull_e{i}", (cx, cy, cz))
    gull_e.rotation_euler = (0, 0, a + math.pi/2)
    # Body
    smooth_sphere(f"gull_b{i}", r=0.20, loc=(0, 0, 0),
                  parent=gull_e, mat_=M_GULL, scale=(2.0, 0.8, 0.8))
    # Head
    smooth_sphere(f"gull_h{i}", r=0.13, loc=(0.30, 0, 0.05),
                  parent=gull_e, mat_=M_GULL)
    # Beak
    smooth_cone(f"gull_bk{i}", r1=0.04, r2=0.005, depth=0.10, segs=8,
                loc=(0.42, 0, 0.02), parent=gull_e, mat_=M_GULL_BEAK)
    # Wings (outstretched - 2 segments per side)
    wing_phase = random.uniform(0, math.pi*2)
    wings = []
    for side in (-1, 1):
        w_e = empty(f"gull_w_e{i}_{side}", (0, side*0.18, 0.05), parent=gull_e)
        beveled_cube(f"gull_w{i}_{side}", (0.20, 0.65, 0.04),
                     bevel_offset=0.02,
                     loc=(0, side*0.33, 0), parent=w_e, mat_=M_GULL)
        # Wing tip darker
        beveled_cube(f"gull_wt{i}_{side}", (0.15, 0.20, 0.03),
                     loc=(0, side*0.70, 0), parent=w_e, mat_=M_GULL_DARK)
        wings.append((w_e, side))
    # Tail
    beveled_cube(f"gull_t{i}", (0.12, 0.20, 0.03),
                 loc=(-0.30, 0, 0), parent=gull_e, mat_=M_GULL)
    seagulls.append({"e": gull_e, "wings": wings, "phase": wing_phase,
                     "orbit_radius": rad, "orbit_speed": random.uniform(0.3, 0.6),
                     "orbit_phase": a, "base_z": cz})

# ============ ANIMATION ============
fps = 30
duration_s = 6
total_frames = fps * duration_s

# Galion balance vagues (bob + roll Y)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    ship_base.location.z = 0.5 + math.sin(t * 1.5) * 0.15
    ship_base.rotation_euler = (
        math.sin(t * 1.2) * math.radians(4),
        math.sin(t * 1.3 + 0.5) * math.radians(3),
        math.radians(-25) + math.sin(t * 0.8) * math.radians(1.5),
    )
    ship_base.keyframe_insert("location", frame=f)
    ship_base.keyframe_insert("rotation_euler", frame=f)

# Sails billow (scale)
sails = [obj for obj in bpy.data.objects if obj.name.startswith("sail_") and "tail" not in obj.name]
for sail in sails:
    if "_phase" not in sail.keys():
        continue
    phase = sail["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        sail.scale.x = 1.5 + math.sin(t * 1.8 + phase) * 0.20
        sail.keyframe_insert("scale", frame=f)

# Jolly roger flag flap (rotation X)
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    flag_e.rotation_euler = (
        math.sin(t * 4.0) * math.radians(20),
        math.sin(t * 3.0 + 0.5) * math.radians(8),
        math.sin(t * 2.5) * math.radians(5),
    )
    flag_e.keyframe_insert("rotation_euler", frame=f)

# Captain gesture (saber raised, sway)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    captain["root"].location.z = 0.6 + math.sin(t * 1.2) * 0.03
    captain["root"].rotation_euler = (0, 0, math.radians(-40) + math.sin(t * 0.8) * math.radians(3))
    captain["root"].keyframe_insert("location", frame=f)
    captain["root"].keyframe_insert("rotation_euler", frame=f)
    # Saber swing
    captain["l_shoulder"].rotation_euler = (
        math.radians(-110) + math.sin(t * 1.5) * math.radians(15),
        0,
        math.radians(15) + math.sin(t * 1.5 + 0.3) * math.radians(8),
    )
    captain["l_shoulder"].keyframe_insert("rotation_euler", frame=f)
    # Hat slight wobble
    captain["hat_e"].rotation_euler = (
        math.sin(t * 0.9) * math.radians(2),
        math.sin(t * 1.1 + 0.5) * math.radians(2),
        0,
    )
    captain["hat_e"].keyframe_insert("rotation_euler", frame=f)

# Parrot wing flap occasionally + head tilt
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    flap = math.sin(t * 5.0) * 0.3 if (t * 0.5) % 2 < 1 else 0
    for w_e in parrot_wings:
        w_e.rotation_euler = (flap, 0, 0)
        w_e.keyframe_insert("rotation_euler", frame=f)
    parrot_head.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(15))
    parrot_head.keyframe_insert("rotation_euler", frame=f)

# Crew animation (right arm raised cheering oscillation + body sway)
for i, c in enumerate(crews):
    phase = i * 0.6
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        c["root"].location.z = 0.5 + math.sin(t * 2.0 + phase) * 0.04
        c["root"].keyframe_insert("location", frame=f)
        # Right shoulder (cheering motion)
        sh = c["root"].children[2 + 2*1]  # naming-dependent, fallback safe
    # Easier: use direct lookup
crew_arms = {}
for c_idx, c in enumerate(crews):
    name = f"crew{c_idx}"
    sh = bpy.data.objects.get(f"{name}_sh1")  # right shoulder
    if sh:
        crew_arms[c_idx] = sh
for c_idx, sh in crew_arms.items():
    phase = c_idx * 0.7
    base_rx = math.radians(-150)
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        sh.rotation_euler = (
            base_rx + math.sin(t * 3.0 + phase) * math.radians(20),
            0,
            math.sin(t * 2.0 + phase) * math.radians(10),
        )
        sh.keyframe_insert("rotation_euler", frame=f)

# Seagulls flap + orbit
for g in seagulls:
    phase = g["phase"]
    radius = g["orbit_radius"]
    speed = g["orbit_speed"]
    base_phase = g["orbit_phase"]
    base_z = g["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Flap
        flap = math.sin(t * 6.0 + phase) * math.radians(40)
        for w_e, side in g["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)
        # Orbit
        a = base_phase + speed * t
        x = radius * math.cos(a)
        y = radius * math.sin(a)
        z = base_z + math.sin(t * 1.5 + phase) * 0.5
        g["e"].location = (x, y, z)
        g["e"].rotation_euler = (0, 0, a + math.pi/2)
        g["e"].keyframe_insert("location", frame=f)
        g["e"].keyframe_insert("rotation_euler", frame=f)

# Palms sway (rotation X+Y) + frond ripple
for pi, p in enumerate(palms):
    phase = pi * 0.8
    base_rx = p.rotation_euler.x
    base_ry = p.rotation_euler.y
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p.rotation_euler = (
            base_rx + math.sin(t * 1.0 + phase) * math.radians(2.5),
            base_ry + math.cos(t * 1.2 + phase) * math.radians(2.0),
            0,
        )
        p.keyframe_insert("rotation_euler", frame=f)

# Gold coins shimmer (scale pulse + Z bob)
coins = [obj for obj in bpy.data.objects if obj.name.startswith("coin")]
for ci, coin in enumerate(coins):
    if "_phase" not in coin.keys():
        continue
    phase = coin["_phase"]
    base_z = coin.location.z
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + phase) * 0.10
        coin.scale = (s, s, s)
        coin.keyframe_insert("scale", frame=f)

# Cascade flow (Z descent cycle + scale)
for ci, cseg in enumerate(cascade_segs):
    base_z = cseg["_base_z"]
    phase = ci * 0.3
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        cseg.location.z = base_z + math.sin(t * 3.0 + phase) * 0.10
        s = 1 + math.sin(t * 4.0 + phase) * 0.08
        cseg.scale = (s, 1, s)
        cseg.keyframe_insert("location", frame=f)
        cseg.keyframe_insert("scale", frame=f)

# Ocean foam pulse (scale Y)
for foam in foams:
    if "_phase" not in foam.keys():
        continue
    phase = foam["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        foam.scale.y = 1 + math.sin(t * 2.5 + phase) * 0.3
        foam.keyframe_insert("scale", frame=f)

# Clouds drift
for ci, cl in enumerate(clouds):
    base_x = cl.location.x
    base_y = cl.location.y
    phase = ci * 0.7
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        cl.location.x = base_x + math.sin(t * 0.4 + phase) * 0.4
        cl.location.y = base_y + math.cos(t * 0.3 + phase) * 0.3
        cl.keyframe_insert("location", frame=f)

# Sun breathe
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.5) * 0.04
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)

# Turtle slight bob + tilt
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    turtle_base.location.z = 0.18 + math.sin(t * 0.8) * 0.015
    turtle_head.rotation_euler = (0, 0, math.sin(t * 1.2) * math.radians(10))
    turtle_base.keyframe_insert("location", frame=f)
    turtle_head.keyframe_insert("rotation_euler", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_pirate_island_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
    export_yup=True,
    use_selection=False,
)

size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_pirate_treasure_island] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_pirate_treasure_island] Galion 3-mast + jolly roger + 6 cannons + captain full anatomy + parrot + 5 crew + treasure chest + 40 coins + 6 palms + cascade + cliff + turtle + 50 seagulls flying")
