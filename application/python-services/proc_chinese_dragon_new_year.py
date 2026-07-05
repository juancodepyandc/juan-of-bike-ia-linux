"""
proc_chinese_dragon_new_year.py — 206e procédural AuroraIA (70e qualité)
Nouvel An chinois : dragon serpentin 20 segs + 8 porteurs + lion dancers + acrobates + lanternes + feux + pagodes
"""
import bpy, bmesh, math, random, os

random.seed(0xCD20660)

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
M_SKY_RED = mat("sky", (0.65, 0.18, 0.20, 1.0), 0.0, 0.7, emission=(0.75,0.22,0.25), emission_strength=2.0)
M_STAR = mat("star", (1.0, 0.95, 0.65, 1.0), 0.0, 0.05, emission=(1.0,0.95,0.65), emission_strength=15.0)
M_MOON = mat("moon", (1.0, 0.85, 0.55, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.55), emission_strength=14.0)
M_GROUND = mat("ground", (0.35, 0.20, 0.15, 1.0), 0.0, 0.80, emission=(0.30,0.18,0.13), emission_strength=0.4)
M_STONE_PATH = mat("path", (0.55, 0.45, 0.35, 1.0), 0.0, 0.70, emission=(0.45,0.35,0.28), emission_strength=0.4)

# Dragon (rainbow scales)
M_DRAGON_GOLD = mat("dragon_g", (1.0, 0.78, 0.25, 1.0), 0.5, 0.30, emission=(0.95,0.72,0.22), emission_strength=2.5)
M_DRAGON_RED = mat("dragon_r", (0.95, 0.15, 0.18, 1.0), 0.0, 0.40, emission=(0.95,0.18,0.20), emission_strength=2.0)
M_DRAGON_GREEN = mat("dragon_g2", (0.18, 0.85, 0.30, 1.0), 0.0, 0.40, emission=(0.20,0.85,0.32), emission_strength=2.0)
M_DRAGON_BLUE = mat("dragon_b", (0.20, 0.50, 0.95, 1.0), 0.0, 0.40, emission=(0.22,0.55,1.0), emission_strength=2.0)
M_DRAGON_PURPLE = mat("dragon_p", (0.75, 0.30, 0.95, 1.0), 0.0, 0.40, emission=(0.80,0.35,1.0), emission_strength=2.2)
M_DRAGON_YELLOW = mat("dragon_y", (1.0, 0.85, 0.20, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.25), emission_strength=2.4)
M_DRAGON_WHITE = mat("dragon_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.45, emission=(0.92,0.88,0.82), emission_strength=1.5)
M_DRAGON_EYE = mat("dragon_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.90,0.25), emission_strength=15.0)
M_DRAGON_TEETH = mat("dragon_t", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40, emission=(0.85,0.82,0.78), emission_strength=0.6)
M_DRAGON_TONGUE = mat("dragon_tongue", (0.85, 0.15, 0.20, 1.0), 0.0, 0.40, emission=(0.80,0.15,0.18), emission_strength=2.5)
M_DRAGON_BEARD = mat("dragon_beard", (0.95, 0.85, 0.30, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.28), emission_strength=1.2)
M_DRAGON_HORN = mat("dragon_horn", (0.85, 0.65, 0.30, 1.0), 0.85, 0.30, emission=(0.78,0.58,0.28), emission_strength=0.8)
M_PEARL = mat("pearl", (0.95, 0.92, 0.95, 1.0), 0.3, 0.20, emission=(0.95,0.95,1.0), emission_strength=8.0)

# Costumes porters
M_COSTUME_RED = mat("costume_r", (0.65, 0.10, 0.10, 1.0), 0.0, 0.55, emission=(0.60,0.10,0.10), emission_strength=0.7)
M_COSTUME_GOLD = mat("costume_g", (0.92, 0.75, 0.25, 1.0), 0.3, 0.40, emission=(0.85,0.68,0.22), emission_strength=0.8)
M_SKIN = mat("skin", (0.92, 0.78, 0.62, 1.0), 0.0, 0.55, emission=(0.82,0.70,0.55), emission_strength=0.3)
M_HAIR_BLACK = mat("hair_bk", (0.06, 0.05, 0.04, 1.0), 0.0, 0.85)
M_HEADBAND = mat("headband", (0.95, 0.18, 0.20, 1.0), 0.0, 0.55, emission=(0.85,0.18,0.18), emission_strength=0.6)

# Lion dance
M_LION_RED = mat("lion_r", (0.95, 0.18, 0.20, 1.0), 0.0, 0.45, emission=(0.95,0.20,0.22), emission_strength=2.5)
M_LION_GOLD = mat("lion_g", (1.0, 0.85, 0.30, 1.0), 0.5, 0.30, emission=(0.95,0.78,0.28), emission_strength=2.0)
M_LION_GREEN = mat("lion_gr", (0.20, 0.85, 0.35, 1.0), 0.0, 0.40, emission=(0.22,0.85,0.35), emission_strength=2.2)
M_LION_FUR = mat("lion_fur", (0.85, 0.40, 0.20, 1.0), 0.0, 0.80, emission=(0.78,0.38,0.18), emission_strength=0.8)

# Lanterns
M_LANTERN_PAPER = mat("lantern_p", (0.95, 0.20, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.30,0.30), emission_strength=10.0)
M_LANTERN_FRAME = mat("lantern_f", (0.15, 0.10, 0.08, 1.0), 0.3, 0.55)
M_LANTERN_TASSEL = mat("lantern_t", (1.0, 0.85, 0.20, 1.0), 0.5, 0.40, emission=(1.0,0.85,0.25), emission_strength=2.0)

# Fireworks
M_FIREWORK_RED = mat("fw_r", (1.0, 0.20, 0.15, 1.0), 0.0, 0.05, emission=(1.0,0.20,0.15), emission_strength=20.0)
M_FIREWORK_GOLD = mat("fw_g", (1.0, 0.85, 0.30, 1.0), 0.0, 0.05, emission=(1.0,0.85,0.30), emission_strength=22.0)
M_FIREWORK_BLUE = mat("fw_b", (0.30, 0.60, 1.0, 1.0), 0.0, 0.05, emission=(0.40,0.70,1.0), emission_strength=20.0)
M_FIREWORK_GREEN = mat("fw_g2", (0.30, 1.0, 0.40, 1.0), 0.0, 0.05, emission=(0.35,1.0,0.45), emission_strength=20.0)
M_FIREWORK_PURPLE = mat("fw_p", (0.85, 0.30, 1.0, 1.0), 0.0, 0.05, emission=(0.90,0.35,1.0), emission_strength=20.0)

# Firecrackers
M_PETARD = mat("petard", (0.85, 0.18, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.18,0.18), emission_strength=0.6)

# Pagodas
M_PAGODA_RED = mat("pag_r", (0.75, 0.15, 0.18, 1.0), 0.0, 0.55, emission=(0.68,0.15,0.15), emission_strength=0.6)
M_PAGODA_GOLD = mat("pag_g", (0.92, 0.75, 0.25, 1.0), 0.7, 0.30, emission=(0.85,0.68,0.22), emission_strength=0.9)
M_PAGODA_ROOF = mat("pag_roof", (0.55, 0.18, 0.18, 1.0), 0.3, 0.50, emission=(0.50,0.18,0.18), emission_strength=0.5)
M_PAGODA_PILLAR = mat("pag_pillar", (0.85, 0.18, 0.18, 1.0), 0.0, 0.50, emission=(0.78,0.18,0.15), emission_strength=0.5)

# Banners
M_BANNER_RED = mat("banner_r", (0.85, 0.15, 0.15, 1.0), 0.0, 0.45, emission=(0.78,0.15,0.13), emission_strength=0.8)
M_BANNER_GOLD = mat("banner_g", (1.0, 0.85, 0.30, 1.0), 0.4, 0.40, emission=(0.95,0.78,0.28), emission_strength=1.0)

# Drums
M_DRUM_BODY = mat("drum_b", (0.65, 0.18, 0.18, 1.0), 0.0, 0.50, emission=(0.58,0.18,0.18), emission_strength=0.6)
M_DRUM_SKIN = mat("drum_sk", (0.92, 0.82, 0.55, 1.0), 0.0, 0.50, emission=(0.85,0.75,0.50), emission_strength=0.5)
M_DRUM_STICK = mat("drum_st", (0.30, 0.18, 0.10, 1.0), 0.0, 0.75)

# Petals
M_PETAL_RED = mat("petal_r", (1.0, 0.25, 0.30, 1.0), 0.0, 0.50, emission=(1.0,0.30,0.30), emission_strength=2.0)
M_PETAL_PINK = mat("petal_p", (1.0, 0.55, 0.70, 1.0), 0.0, 0.50, emission=(1.0,0.55,0.65), emission_strength=1.5)

# Sparks
M_SPARK = mat("spark", (1.0, 0.85, 0.30, 1.0), 0.0, 0.05, emission=(1.0,0.90,0.40), emission_strength=18.0)
M_SMOKE = mat("smoke", (0.35, 0.30, 0.30, 1.0), 0.0, 0.85, emission=(0.30,0.25,0.25), emission_strength=0.5, alpha=0.5)

# ============ SKY + MOON + STARS ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_RED, scale=(1,1,0.6))
sky.scale = (1,1,0.6)
moon = smooth_sphere("moon", r=2.8, loc=(-15, 38, 28), mat_=M_MOON)
# 80 stars
for i in range(80):
    sx = random.uniform(-50, 50)
    sy = random.uniform(15, 45)
    sz = random.uniform(18, 38)
    star = smooth_sphere(f"star{i}", r=random.uniform(0.08, 0.18), segs=8, rings=6,
                        loc=(sx, sy, sz), mat_=M_STAR)
    star["_phase"] = random.uniform(0, math.pi*2)

# Ground (street stone)
ground = beveled_cube("ground", (60, 60, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), mat_=M_GROUND)
# Stone path central
beveled_cube("path", (8, 50, 0.10), loc=(0, 0, 0.05), mat_=M_STONE_PATH)
# Path tiles (alternance gold)
for i in range(20):
    beveled_cube(f"tile{i}", (7.5, 0.05, 0.10), loc=(0, -23 + i*2.5, 0.06), mat_=M_PAGODA_GOLD)

# ============ CHINESE DRAGON (20 segments serpentine) ============
dragon_e = empty("dragon", loc=(0, 0, 4.0))

# Dragon body 20 segments serpentine arc
dragon_segs = []
seg_colors = [M_DRAGON_RED, M_DRAGON_GOLD, M_DRAGON_GREEN, M_DRAGON_BLUE, M_DRAGON_PURPLE, M_DRAGON_YELLOW]
for i in range(20):
    t = i / 19.0
    sx = -18 + t * 36
    sy = math.sin(t * math.pi * 3.5) * 4.0  # serpentine wave
    sz = 4.0 + math.sin(t * math.pi * 2) * 1.2  # vertical wave too
    color = seg_colors[i % 6]
    # Body sphere
    body_seg = smooth_sphere(f"d_body{i}", r=0.65, segs=22, rings=14,
                              loc=(sx, sy, sz), parent=dragon_e, mat_=color,
                              scale=(1.0, 1.4, 1.0))
    # Belly lighter underneath
    smooth_sphere(f"d_belly{i}", r=0.55, loc=(sx, sy, sz - 0.20),
                  parent=dragon_e, mat_=M_DRAGON_YELLOW, scale=(0.8, 1.2, 0.5))
    # Dorsal ridge (3 spines)
    for j in range(3):
        spine = beveled_cube(f"d_spine{i}_{j}", (0.10, 0.10, 0.35), bevel_offset=0.02,
                            loc=(sx, sy - 0.10 + j*0.10, sz + 0.65),
                            parent=dragon_e, mat_=M_DRAGON_GOLD)
    # Scale band (gold ring)
    if i % 2 == 0:
        cyl(f"d_scale_band{i}", r=0.68, depth=0.05, segs=20,
            loc=(sx, sy, sz), parent=dragon_e, mat_=M_DRAGON_GOLD).rotation_euler = (math.radians(90), 0, 0)
    # Small fin/leg pair (every 5 segs)
    if i % 5 == 0:
        for side in (-1, 1):
            # Tiny leg
            leg = smooth_cone(f"d_leg{i}_{side}", r1=0.18, r2=0.08, depth=0.35, segs=10,
                             loc=(sx, sy + side*0.6, sz - 0.25), parent=dragon_e, mat_=color)
            leg.rotation_euler = (math.radians(side*-25), 0, 0)
            # 3 claws gold
            for c in range(3):
                smooth_cone(f"d_claw{i}_{side}_{c}", r1=0.04, r2=0.005, depth=0.10, segs=6,
                            loc=(sx + (c-1)*0.06, sy + side*0.75, sz - 0.45),
                            parent=dragon_e, mat_=M_DRAGON_GOLD).rotation_euler = (math.radians(80), 0, 0)
    dragon_segs.append((body_seg, sx, sy, sz, i))

# DRAGON HEAD (large at end)
head_x = 18; head_y = math.sin(math.pi * 3.5) * 4.0; head_z = 4.0 + math.sin(math.pi * 2) * 1.2
head_e = empty("dragon_head_e", (head_x + 1.2, head_y, head_z))
# Main skull
smooth_sphere("dragon_head_main", r=1.2, segs=28, rings=18, loc=(0, 0, 0),
              parent=head_e, mat_=M_DRAGON_RED, scale=(1.0, 1.6, 1.1))
# Belly lighter underside
smooth_sphere("dragon_head_belly", r=1.0, loc=(0, -0.20, -0.40),
              parent=head_e, mat_=M_DRAGON_YELLOW, scale=(1.0, 1.0, 0.5))
# 2 HUGE EYES (signature)
for side in (-1, 1):
    # White
    smooth_sphere(f"dragon_eye_w_{side}", r=0.30, loc=(side*0.50, -0.80, 0.45),
                  parent=head_e, mat_=M_DRAGON_WHITE)
    # Iris yellow émissif
    smooth_sphere(f"dragon_eye_i_{side}", r=0.24, loc=(side*0.50, -0.95, 0.45),
                  parent=head_e, mat_=M_DRAGON_EYE)
    # Pupil black
    smooth_sphere(f"dragon_pup_{side}", r=0.10, loc=(side*0.50, -1.10, 0.45),
                  parent=head_e, mat_=mat(f"dp{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Eyelid ridge gold
    smooth_sphere(f"dragon_lid_{side}", r=0.35, loc=(side*0.50, -0.70, 0.70),
                  parent=head_e, mat_=M_DRAGON_GOLD, scale=(1, 1, 0.3))

# 2 BIG HORNS curved (signature Chinese dragon)
for side in (-1, 1):
    h_e = empty(f"horn_e_{side}", (side*0.50, 0.30, 0.90), parent=head_e)
    h_e.rotation_euler = (math.radians(-30), math.radians(side*25), 0)
    # Multi-seg curved horn
    for s in range(4):
        seg = smooth_cone(f"horn_{side}_{s}", r1=0.15 - s*0.025, r2=0.10 - s*0.025, depth=0.30, segs=10,
                          loc=(0, 0, s*0.30 + 0.15), parent=h_e, mat_=M_DRAGON_HORN)
        seg.rotation_euler = (math.radians(-12*s), 0, 0)

# BEARD GOLD (signature flowing)
beard_e = empty("beard_e", (0, -0.50, -0.85), parent=head_e)
for j in range(8):
    a = (j - 3.5) * 0.12
    smooth_sphere(f"beard{j}", r=0.10 - abs(j-3.5)*0.008,
                  loc=(0.50*math.sin(a), 0, -j*0.20),
                  parent=beard_e, mat_=M_DRAGON_BEARD, scale=(1, 1.3, 1.2))

# TEETH (top + bottom rows, 8 each)
for r in (-1, 1):
    z_off = 0.30 if r == -1 else -0.30
    for j in range(8):
        tx = (j - 3.5) * 0.18
        smooth_cone(f"teeth_{r}_{j}", r1=0.06, r2=0.005, depth=0.18, segs=8,
                    loc=(tx, -1.20, z_off - r*0.10), parent=head_e, mat_=M_DRAGON_TEETH).rotation_euler = (math.radians(150 if r == -1 else 30), 0, 0)

# Open mouth (jaw lower)
jaw_e = empty("jaw_e", (0, -0.20, -0.30), parent=head_e)
jaw_e.rotation_euler = (math.radians(25), 0, 0)
smooth_sphere("jaw_main", r=0.95, loc=(0, -0.50, -0.20),
              parent=jaw_e, mat_=M_DRAGON_RED, scale=(1, 1.2, 0.5))

# TONGUE flowing
tongue_e = empty("tongue_e", (0, -1.20, -0.30), parent=head_e)
for j in range(5):
    smooth_sphere(f"tongue{j}", r=0.18 - j*0.02, loc=(0, -j*0.20, -j*0.05),
                  parent=tongue_e, mat_=M_DRAGON_TONGUE, scale=(1.2, 1.4, 0.5))

# WHISKERS / barbels (4, signature)
for side in (-1, 1):
    for j in range(2):
        wh = beveled_cube(f"whisker_{side}_{j}", (0.04, 0.04, 1.5), bevel_offset=0.01,
                          loc=(side*0.20 + j*0.10*side, -1.20, 0.30),
                          parent=head_e, mat_=M_DRAGON_GOLD)
        wh.rotation_euler = (math.radians(60), 0, math.radians(side*30))

# Mane (multi spheres around head signature lion-like)
for j in range(12):
    a = (j / 12.0) * math.pi * 2
    smooth_sphere(f"mane{j}", r=0.25, loc=(0.95*math.cos(a), 0.40, 0.30 + 0.85*math.sin(a)),
                  parent=head_e, mat_=M_DRAGON_GOLD)

# PEARL (Dragon chasing pearl - signature symbol)
pearl_e = empty("pearl_e", (head_x + 4.5, head_y, head_z + 1.5))
smooth_sphere("pearl_main", r=0.55, segs=24, rings=18, loc=(0, 0, 0),
              parent=pearl_e, mat_=M_PEARL)
# 4 halos
for i in range(4):
    smooth_sphere(f"pearl_halo{i}", r=0.55 + (i+1)*0.20, loc=(0, 0, 0),
                  parent=pearl_e, mat_=M_PEARL, scale=(1, 1, 1))

# ============ 8 PORTERS sous dragon avec poles ============
porters = []
for i in range(8):
    t = (i + 1) / 9.0
    sx = -16 + t * 32
    sy = math.sin(t * math.pi * 3.5) * 4.0
    p_e = empty(f"porter{i}", (sx, sy, 0))
    # Pole vertical (lifts dragon)
    cyl(f"porter_pole{i}", r=0.05, depth=3.5, segs=10,
        loc=(0, 0, 1.75), parent=p_e, mat_=M_DRUM_STICK)
    # Body (red costume)
    cyl(f"porter_leg_l{i}", r=0.10, depth=0.85, segs=10,
        loc=(-0.13, 0, 0.42), parent=p_e, mat_=M_COSTUME_RED)
    cyl(f"porter_leg_r{i}", r=0.10, depth=0.85, segs=10,
        loc=(0.13, 0, 0.42), parent=p_e, mat_=M_COSTUME_RED)
    # Torso costume + gold sash
    beveled_cube(f"porter_t{i}", (0.50, 0.30, 0.80), bevel_offset=0.05,
                 loc=(0, 0, 1.30), parent=p_e, mat_=M_COSTUME_RED)
    beveled_cube(f"porter_sash{i}", (0.55, 0.34, 0.10), loc=(0, 0, 1.10),
                 parent=p_e, mat_=M_COSTUME_GOLD)
    # Head
    head_p = empty(f"porter_h_e{i}", (0, 0, 1.85), parent=p_e)
    smooth_sphere(f"porter_h{i}", r=0.18, loc=(0, 0, 0), parent=head_p, mat_=M_SKIN)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"porter_eye{i}_{side}", r=0.025,
                      loc=(side*0.06, -0.14, 0.03), parent=head_p,
                      mat_=mat(f"pew{i}{side}", (0.95,0.92,0.85,1), 0, 0.4))
    # Black hair
    smooth_sphere(f"porter_hair{i}", r=0.20, loc=(0, 0.03, 0.05),
                  parent=head_p, mat_=M_HAIR_BLACK, scale=(1.05, 1.0, 0.85))
    # Red headband
    cyl(f"porter_band{i}", r=0.21, depth=0.04, segs=18,
        loc=(0, 0, 0.05), parent=head_p, mat_=M_HEADBAND)
    # 2 arms raised holding pole
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"porter_sh{i}_{side_idx}", (side*0.25, 0, 1.75), parent=p_e)
        sh.rotation_euler = (math.radians(-150), 0, math.radians(side*-10))
        cyl(f"porter_up{i}_{side_idx}", r=0.07, depth=0.35, segs=8,
            loc=(0, 0, -0.18), parent=sh, mat_=M_COSTUME_RED)
        cyl(f"porter_fa{i}_{side_idx}", r=0.06, depth=0.32, segs=8,
            loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN)
    porters.append({"e": p_e, "head": head_p, "phase": i * 0.4})

# ============ 4 SMALLER DRAGONS (côtés du grand dragon) ============
mini_dragons = []
for di in range(4):
    a = (di / 4.0) * math.pi * 2
    rad = 14
    mx = math.cos(a) * rad
    my = math.sin(a) * rad
    md_e = empty(f"mini_dragon{di}", (mx, my, 5.0))
    md_color = [M_DRAGON_GREEN, M_DRAGON_BLUE, M_DRAGON_PURPLE, M_DRAGON_RED][di]
    # 10 segments serpentine
    for i in range(10):
        t = i / 9.0
        seg_x = (t - 0.5) * 6
        seg_y = math.sin(t * math.pi * 2.5) * 1.5
        seg_z = math.sin(t * math.pi * 1.5) * 0.6
        smooth_sphere(f"md{di}_s{i}", r=0.30, segs=18, rings=12,
                      loc=(seg_x, seg_y, seg_z), parent=md_e, mat_=md_color,
                      scale=(1, 1.4, 1))
        if i % 2 == 0:
            cyl(f"md{di}_b{i}", r=0.32, depth=0.03, segs=14,
                loc=(seg_x, seg_y, seg_z), parent=md_e, mat_=M_DRAGON_GOLD).rotation_euler = (math.radians(90), 0, 0)
    # Head
    md_head_e = empty(f"md{di}_head_e", (3.5, 0, 0), parent=md_e)
    smooth_sphere(f"md{di}_h", r=0.45, segs=20, rings=14, loc=(0, 0, 0),
                  parent=md_head_e, mat_=md_color, scale=(1, 1.5, 1))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"md{di}_eye_{side}", r=0.10, loc=(side*0.20, -0.35, 0.20),
                      parent=md_head_e, mat_=M_DRAGON_EYE)
    # Horns
    for side in (-1, 1):
        smooth_cone(f"md{di}_horn_{side}", r1=0.06, r2=0.005, depth=0.30, segs=8,
                    loc=(side*0.18, 0.20, 0.45), parent=md_head_e, mat_=M_DRAGON_HORN).rotation_euler = (math.radians(-30), 0, 0)
    # Whiskers
    for side in (-1, 1):
        beveled_cube(f"md{di}_wh_{side}", (0.02, 0.02, 0.60),
                     loc=(side*0.08, -0.45, 0.10), parent=md_head_e, mat_=M_DRAGON_GOLD).rotation_euler = (math.radians(70), 0, math.radians(side*20))
    md_e["_phase"] = di * 1.0
    mini_dragons.append(md_e)

# ============ 2 DANCING LIONS ============
lion_dancers = []
for li in range(2):
    lx = -7 + li * 14
    ly = -6
    l_e = empty(f"lion{li}", (lx, ly, 0))
    # Lion head (big mask)
    color = M_LION_RED if li == 0 else M_LION_GREEN
    head_l_e = empty(f"lion_head_e{li}", (0, 0, 1.8), parent=l_e)
    smooth_sphere(f"lion_h{li}", r=0.55, segs=24, rings=16, loc=(0, 0, 0),
                  parent=head_l_e, mat_=color, scale=(1.1, 1.0, 1.0))
    # 2 large bulging eyes
    for side in (-1, 1):
        smooth_sphere(f"lion_eye_w{li}_{side}", r=0.20, loc=(side*0.25, -0.45, 0.18),
                      parent=head_l_e, mat_=M_DRAGON_WHITE)
        smooth_sphere(f"lion_eye_i{li}_{side}", r=0.14, loc=(side*0.25, -0.55, 0.18),
                      parent=head_l_e, mat_=M_DRAGON_EYE)
        smooth_sphere(f"lion_pup{li}_{side}", r=0.06, loc=(side*0.25, -0.65, 0.18),
                      parent=head_l_e, mat_=mat(f"lp{li}{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # Big nose
    smooth_sphere(f"lion_nose{li}", r=0.18, loc=(0, -0.55, -0.10),
                  parent=head_l_e, mat_=M_LION_GOLD)
    # Open mouth large
    smooth_sphere(f"lion_mouth{li}", r=0.30, loc=(0, -0.40, -0.40),
                  parent=head_l_e, mat_=M_DRAGON_RED, scale=(1.2, 1.2, 0.5))
    # Teeth
    for j in range(6):
        tx = (j - 2.5) * 0.10
        smooth_cone(f"lion_t{li}_{j}", r1=0.04, r2=0.005, depth=0.12, segs=6,
                    loc=(tx, -0.55, -0.35), parent=head_l_e, mat_=M_DRAGON_TEETH).rotation_euler = (math.radians(150), 0, 0)
    # MANE (12 fur tufts radiating)
    for j in range(16):
        a = (j / 16.0) * math.pi * 2
        smooth_sphere(f"lion_mane{li}_{j}", r=0.18,
                      loc=(0.6*math.cos(a), 0.0, 0.0 + 0.6*math.sin(a)),
                      parent=head_l_e, mat_=M_LION_FUR)
    # 2 ears
    for side in (-1, 1):
        smooth_sphere(f"lion_ear{li}_{side}", r=0.12, loc=(side*0.35, 0.20, 0.45),
                      parent=head_l_e, mat_=color)
    # 2 small horns
    for side in (-1, 1):
        smooth_cone(f"lion_horn{li}_{side}", r1=0.05, r2=0.005, depth=0.20, segs=8,
                    loc=(side*0.15, 0.15, 0.65), parent=head_l_e, mat_=M_DRAGON_HORN).rotation_euler = (math.radians(-20), 0, 0)
    # Body cloth (long fabric trailing)
    body_e = empty(f"lion_body_e{li}", (0, 0.5, 1.0), parent=l_e)
    # 4 panel cloth body
    for j in range(4):
        beveled_cube(f"lion_cloth{li}_{j}", (0.65, 1.0, 0.05), bevel_offset=0.02,
                     loc=(0, 0.8 + j*0.6, 0.5 - j*0.10), parent=body_e, mat_=color)
    # Fur tufts on cloth
    for j in range(8):
        a = random.uniform(0, math.pi*2)
        smooth_sphere(f"lion_cl_fur{li}_{j}", r=0.08,
                      loc=(random.uniform(-0.3, 0.3), 0.8 + j*0.3, 0.5),
                      parent=body_e, mat_=M_LION_FUR)
    # 4 LEGS (dancers under)
    # Front dancer (2 legs)
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"lion_fl{li}_{side_idx}", r=0.10, depth=1.0, segs=10,
            loc=(side*0.15, 0, 0.5), parent=l_e, mat_=M_COSTUME_RED)
        beveled_cube(f"lion_fs{li}_{side_idx}", (0.18, 0.25, 0.10),
                     loc=(side*0.15, 0.04, 0.05), parent=l_e, mat_=M_COSTUME_RED)
    # Back dancer (2 legs further back)
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"lion_bl{li}_{side_idx}", r=0.10, depth=1.0, segs=10,
            loc=(side*0.15, 1.8, 0.5), parent=l_e, mat_=M_COSTUME_RED)
        beveled_cube(f"lion_bs{li}_{side_idx}", (0.18, 0.25, 0.10),
                     loc=(side*0.15, 1.84, 0.05), parent=l_e, mat_=M_COSTUME_RED)
    lion_dancers.append({"e": l_e, "head": head_l_e, "phase": li * 1.0})

# ============ 6 ACROBATES (acrobats flipping) ============
acrobats = []
for i in range(6):
    a = (i / 6.0) * math.pi * 2 + 0.5
    rad = 10
    ax = math.cos(a) * rad
    ay = math.sin(a) * rad - 5
    facing = a + math.pi
    a_e = empty(f"acrobat{i}", (ax, ay, 1.5))
    a_e.rotation_euler = (0, 0, facing)
    # Body (red costume)
    cyl(f"ac_leg_l{i}", r=0.10, depth=0.85, segs=10,
        loc=(-0.13, 0, -1.0), parent=a_e, mat_=M_COSTUME_RED)
    cyl(f"ac_leg_r{i}", r=0.10, depth=0.85, segs=10,
        loc=(0.13, 0, -1.0), parent=a_e, mat_=M_COSTUME_RED)
    beveled_cube(f"ac_t{i}", (0.50, 0.30, 0.80), bevel_offset=0.05,
                 loc=(0, 0, -0.1), parent=a_e, mat_=M_COSTUME_GOLD)
    # Sash
    beveled_cube(f"ac_sash{i}", (0.55, 0.34, 0.10), loc=(0, 0, -0.30),
                 parent=a_e, mat_=M_HEADBAND)
    # Head
    head_a = empty(f"ac_h_e{i}", (0, 0, 0.45), parent=a_e)
    smooth_sphere(f"ac_h{i}", r=0.18, loc=(0,0,0), parent=head_a, mat_=M_SKIN)
    for side in (-1, 1):
        smooth_sphere(f"ac_eye{i}_{side}", r=0.025,
                      loc=(side*0.06, -0.14, 0.03), parent=head_a,
                      mat_=mat(f"acew{i}{side}", (0.95,0.92,0.85,1), 0, 0.4))
    smooth_sphere(f"ac_hair{i}", r=0.20, loc=(0, 0.03, 0.05),
                  parent=head_a, mat_=M_HAIR_BLACK, scale=(1.05, 1.0, 0.85))
    cyl(f"ac_band{i}", r=0.21, depth=0.04, segs=18,
        loc=(0, 0, 0.05), parent=head_a, mat_=M_HEADBAND)
    # Arms outstretched
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"ac_sh{i}_{side_idx}", (side*0.30, 0, 0.30), parent=a_e)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-30))
        cyl(f"ac_up{i}_{side_idx}", r=0.07, depth=0.35, segs=8,
            loc=(0, 0, -0.18), parent=sh, mat_=M_COSTUME_GOLD)
        cyl(f"ac_fa{i}_{side_idx}", r=0.06, depth=0.32, segs=8,
            loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN)
    acrobats.append({"e": a_e, "head": head_a, "phase": i * 0.8})

# ============ 4 DRUMMERS ============
drummers = []
for i in range(4):
    dx = -10 + i * 7
    dy = -12
    d_e = empty(f"drummer{i}", (dx, dy, 0))
    # Body
    for side_idx, side in enumerate((-1, 1)):
        cyl(f"dr_leg{i}_{side_idx}", r=0.10, depth=0.85, segs=10,
            loc=(side*0.13, 0, 0.42), parent=d_e, mat_=M_COSTUME_RED)
    beveled_cube(f"dr_t{i}", (0.50, 0.30, 0.80), bevel_offset=0.05,
                 loc=(0, 0, 1.30), parent=d_e, mat_=M_COSTUME_RED)
    # Head
    head_d = empty(f"dr_h_e{i}", (0, 0, 1.85), parent=d_e)
    smooth_sphere(f"dr_h{i}", r=0.18, loc=(0,0,0), parent=head_d, mat_=M_SKIN)
    smooth_sphere(f"dr_hair{i}", r=0.20, loc=(0, 0.03, 0.05),
                  parent=head_d, mat_=M_HAIR_BLACK, scale=(1.05, 1.0, 0.85))
    cyl(f"dr_band{i}", r=0.21, depth=0.04, segs=18,
        loc=(0, 0, 0.05), parent=head_d, mat_=M_HEADBAND)
    # DRUM in front (large red barrel)
    drum_e = empty(f"dr_drum_e{i}", (0, -0.55, 0.65), parent=d_e)
    cyl(f"dr_drum_body{i}", r=0.40, depth=0.65, segs=20,
        loc=(0, 0, 0), parent=drum_e, mat_=M_DRUM_BODY)
    cyl(f"dr_drum_top{i}", r=0.42, depth=0.05, segs=20,
        loc=(0, 0, 0.32), parent=drum_e, mat_=M_DRUM_SKIN)
    # Gold rivets
    for j in range(8):
        a = (j / 8.0) * math.pi * 2
        smooth_sphere(f"dr_rivet{i}_{j}", r=0.03,
                      loc=(0.40*math.cos(a), 0.40*math.sin(a), 0.30),
                      parent=drum_e, mat_=M_DRAGON_GOLD)
    # 2 arms holding sticks
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"dr_sh{i}_{side_idx}", (side*0.22, 0, 1.75), parent=d_e)
        sh.rotation_euler = (math.radians(-90), 0, math.radians(side*-15))
        cyl(f"dr_up{i}_{side_idx}", r=0.07, depth=0.35, segs=8,
            loc=(0, 0, -0.18), parent=sh, mat_=M_COSTUME_RED)
        cyl(f"dr_fa{i}_{side_idx}", r=0.06, depth=0.32, segs=8,
            loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN)
        # Stick
        cyl(f"dr_stick{i}_{side_idx}", r=0.02, depth=0.30, segs=6,
            loc=(0, 0, -0.85), parent=sh, mat_=M_DRUM_STICK)
    drummers.append({"e": d_e, "drum": drum_e, "phase": i * 0.5})

# ============ 30 LANTERNS RED (hanging from string overhead) ============
lanterns = []
# Two strings - left + right
for string_idx, sy_base in enumerate((-3, 3)):
    # String (cable)
    cyl(f"lantern_string{string_idx}", r=0.025, depth=40, segs=8,
        loc=(0, sy_base, 8), mat_=M_LANTERN_FRAME).rotation_euler = (0, math.radians(90), 0)
    for li in range(15):
        lx = (li - 7) * 2.5
        l_e = empty(f"lantern{string_idx}_{li}", (lx, sy_base, 7.5))
        # String to lantern (cord)
        cyl(f"lant_cord{string_idx}_{li}", r=0.01, depth=0.50, segs=6,
            loc=(0, 0, 0.25), parent=l_e, mat_=M_LANTERN_FRAME)
        # Top cap
        cyl(f"lant_top{string_idx}_{li}", r=0.10, depth=0.06, segs=14,
            loc=(0, 0, 0), parent=l_e, mat_=M_LANTERN_FRAME)
        # Body (round paper lantern)
        smooth_sphere(f"lant_body{string_idx}_{li}", r=0.30, segs=18, rings=12,
                      loc=(0, 0, -0.35), parent=l_e, mat_=M_LANTERN_PAPER,
                      scale=(1, 1, 0.85))
        # Frame stripes (3 horizontal)
        for fi in range(3):
            cyl(f"lant_fr{string_idx}_{li}_{fi}", r=0.31, depth=0.02, segs=18,
                loc=(0, 0, -0.45 + fi*0.20), parent=l_e, mat_=M_LANTERN_FRAME).rotation_euler = (math.radians(90), 0, 0)
        # Bottom cap
        cyl(f"lant_bot{string_idx}_{li}", r=0.10, depth=0.06, segs=14,
            loc=(0, 0, -0.70), parent=l_e, mat_=M_LANTERN_FRAME)
        # Tassel hanging
        cyl(f"lant_tas{string_idx}_{li}", r=0.01, depth=0.15, segs=6,
            loc=(0, 0, -0.80), parent=l_e, mat_=M_LANTERN_TASSEL)
        # Tassel ball
        smooth_sphere(f"lant_tas_b{string_idx}_{li}", r=0.05,
                      loc=(0, 0, -0.92), parent=l_e, mat_=M_LANTERN_TASSEL)
        l_e["_phase"] = random.uniform(0, math.pi*2)
        lanterns.append(l_e)

# ============ 50 FIREWORKS (exploding bursts) ============
fireworks = []
firework_mats = [M_FIREWORK_RED, M_FIREWORK_GOLD, M_FIREWORK_BLUE,
                 M_FIREWORK_GREEN, M_FIREWORK_PURPLE]
for fi in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 22)
    fx = math.cos(a) * rad
    fy = math.sin(a) * rad
    fz = random.uniform(12, 22)
    color = random.choice(firework_mats)
    fw_e = empty(f"fw_e{fi}", (fx, fy, fz))
    # Center bright sphere
    smooth_sphere(f"fw_center{fi}", r=0.20, loc=(0, 0, 0),
                  parent=fw_e, mat_=color)
    # 16 radiating bursts
    for j in range(16):
        ja = (j / 16.0) * math.pi * 2
        jb = random.uniform(-0.3, 0.3)
        smooth_sphere(f"fw_burst{fi}_{j}", r=0.08,
                      loc=(math.cos(ja)*math.cos(jb)*1.5,
                           math.sin(ja)*math.cos(jb)*1.5,
                           math.sin(jb)*1.5),
                      parent=fw_e, mat_=color)
    fw_e["_phase"] = random.uniform(0, math.pi*2)
    fw_e["_speed"] = random.uniform(0.8, 1.8)
    fireworks.append(fw_e)

# ============ 20 FIRECRACKER STRINGS (signature petards rouges) ============
for ci in range(2):
    pole_x = -12 + ci * 24
    pole_e = empty(f"petard_pole{ci}", (pole_x, -8, 0))
    # Wooden pole
    cyl(f"petard_pole_shaft{ci}", r=0.08, depth=6, segs=10,
        loc=(0, 0, 3), parent=pole_e, mat_=M_DRUM_STICK)
    # Hanging string of 10 firecrackers
    for pi in range(10):
        pet = cyl(f"petard{ci}_{pi}", r=0.05, depth=0.20, segs=8,
                 loc=(0, 0, 5.5 - pi*0.25), parent=pole_e, mat_=M_PETARD)
        # Tied with string
    # Long fuse hanging
    cyl(f"petard_fuse{ci}", r=0.01, depth=0.30, segs=6,
        loc=(0, 0, 2.8), parent=pole_e, mat_=M_LANTERN_FRAME)

# ============ 3 PAGODAS (background) ============
pagodas = []
for pi in range(3):
    px = -18 + pi * 18
    py = 15
    pag_e = empty(f"pagoda{pi}", (px, py, 0))
    # Base square
    beveled_cube(f"pag_base{pi}", (3.5, 3.5, 0.6), bevel_offset=0.08,
                 loc=(0, 0, 0.30), parent=pag_e, mat_=M_PAGODA_RED)
    # 4 levels
    cum_z = 0.60
    level_sizes = [3.2, 2.8, 2.4, 1.8]
    for li, sz in enumerate(level_sizes):
        # Pillars (4 corners)
        for x_idx, x in enumerate((-1, 1)):
            for y_idx, y in enumerate((-1, 1)):
                cyl(f"pag_pillar{pi}_{li}_{x_idx}{y_idx}", r=0.10, depth=1.4, segs=10,
                    loc=(x*sz/2, y*sz/2, cum_z + 0.7), parent=pag_e, mat_=M_PAGODA_PILLAR)
        # Body wall
        beveled_cube(f"pag_body{pi}_{li}", (sz - 0.3, sz - 0.3, 1.2), bevel_offset=0.05,
                     loc=(0, 0, cum_z + 0.6), parent=pag_e, mat_=M_PAGODA_RED)
        # Roof (sloped pagoda style with upturned eaves)
        roof = beveled_cube(f"pag_roof{pi}_{li}", (sz + 0.4, sz + 0.4, 0.20), bevel_offset=0.08,
                           loc=(0, 0, cum_z + 1.4), parent=pag_e, mat_=M_PAGODA_ROOF)
        # 4 upturned corners (signature pagoda)
        for x_idx, x in enumerate((-1, 1)):
            for y_idx, y in enumerate((-1, 1)):
                # Small turned tip
                tip = beveled_cube(f"pag_tip{pi}_{li}_{x_idx}{y_idx}", (0.15, 0.15, 0.30),
                                   loc=(x*(sz+0.2)/2, y*(sz+0.2)/2, cum_z + 1.55),
                                   parent=pag_e, mat_=M_PAGODA_GOLD)
                tip.rotation_euler = (math.radians(x*y*15), 0, 0)
        cum_z += 1.6
    # Spire top
    smooth_cone(f"pag_spire{pi}", r1=0.20, r2=0.02, depth=1.5, segs=12,
                loc=(0, 0, cum_z + 0.75), parent=pag_e, mat_=M_PAGODA_GOLD)
    smooth_sphere(f"pag_top{pi}", r=0.15, loc=(0, 0, cum_z + 1.55),
                  parent=pag_e, mat_=M_PAGODA_GOLD)
    pagodas.append(pag_e)

# ============ 12 BANNERS (vertical hanging) ============
banners = []
banner_positions = []
for i in range(12):
    a = (i / 12.0) * math.pi * 2
    rad = 16
    bx, by = math.cos(a)*rad, math.sin(a)*rad - 4
    # Avoid pagoda area
    if abs(by - 11) < 4 and abs(bx) < 15:
        by = -5
    banner_positions.append((bx, by))
for bi, (bx, by) in enumerate(banner_positions):
    b_e = empty(f"banner{bi}", (bx, by, 0))
    # Pole
    cyl(f"banner_pole{bi}", r=0.06, depth=6, segs=10,
        loc=(0, 0, 3), parent=b_e, mat_=M_DRUM_STICK)
    # Cross piece at top
    beveled_cube(f"banner_cross{bi}", (0.05, 0.8, 0.05), loc=(0, 0, 5.8),
                 parent=b_e, mat_=M_DRUM_STICK)
    # Banner cloth red
    banner = beveled_cube(f"banner_cloth{bi}", (0.04, 0.5, 2.0), bevel_offset=0.02,
                         loc=(0, 0.30, 4.5), parent=b_e, mat_=M_BANNER_RED)
    # Gold character symbol
    beveled_cube(f"banner_char_v{bi}", (0.06, 0.04, 0.40), loc=(0, 0.30, 4.5),
                 parent=b_e, mat_=M_BANNER_GOLD)
    beveled_cube(f"banner_char_h{bi}", (0.06, 0.30, 0.06), loc=(0, 0.30, 4.5),
                 parent=b_e, mat_=M_BANNER_GOLD)
    # Trim ball top
    smooth_sphere(f"banner_orb{bi}", r=0.08, loc=(0, 0, 6.05),
                  parent=b_e, mat_=M_BANNER_GOLD)
    # Fringe
    for fi in range(5):
        smooth_sphere(f"banner_fringe{bi}_{fi}", r=0.025,
                      loc=(0, 0.30 + (fi-2)*0.10, 3.50), parent=b_e, mat_=M_BANNER_GOLD)
    b_e["_phase"] = bi * 0.4
    banners.append(b_e)

# ============ 200 PETALS RED (falling celebration) ============
petals = []
for i in range(200):
    px = random.uniform(-22, 22)
    py = random.uniform(-22, 22)
    pz = random.uniform(2, 18)
    color = M_PETAL_RED if random.random() < 0.6 else M_PETAL_PINK
    pt = beveled_cube(f"petal{i}", (0.10, 0.14, 0.02), bevel_offset=0.01,
                     loc=(px, py, pz), mat_=color)
    pt.rotation_euler = (random.uniform(0, math.pi*2),
                         random.uniform(0, math.pi*2),
                         random.uniform(0, math.pi*2))
    pt["_phase"] = random.uniform(0, math.pi*2)
    pt["_base_x"] = px; pt["_base_y"] = py; pt["_base_z"] = pz
    pt["_speed"] = random.uniform(0.5, 1.2)
    petals.append(pt)

# ============ 40 SPARKS (from fireworks/firecrackers) ============
sparks = []
for i in range(40):
    sx = random.uniform(-20, 20)
    sy = random.uniform(-20, 20)
    sz = random.uniform(3, 18)
    sp = smooth_sphere(f"spark{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                      loc=(sx, sy, sz), mat_=M_SPARK)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_base_x"] = sx; sp["_base_y"] = sy; sp["_base_z"] = sz
    sp["_speed"] = random.uniform(0.8, 2.0)
    sparks.append(sp)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Dragon body undulation (propagated wave + horizontal serpentine motion)
for i, (body_seg, sx, sy, sz, idx) in enumerate(dragon_segs):
    phase = idx * 0.3
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Y oscillates with phase offset propagating
        new_y = sy + math.sin(t * 1.8 + phase) * 1.5
        new_z = sz + math.sin(t * 1.5 + phase + 0.5) * 0.8
        body_seg.location = (sx, new_y, new_z)
        body_seg.keyframe_insert("location", frame=f)

# Dragon head follows
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    last_seg = dragon_segs[-1]
    new_y_h = last_seg[2] + math.sin(t * 1.8 + 19 * 0.3) * 1.5
    new_z_h = last_seg[3] + math.sin(t * 1.5 + 19 * 0.3 + 0.5) * 0.8
    head_e.location = (last_seg[1] + 1.2, new_y_h, new_z_h)
    head_e.rotation_euler = (0, 0, math.sin(t * 1.2) * math.radians(15))
    head_e.keyframe_insert("location", frame=f)
    head_e.keyframe_insert("rotation_euler", frame=f)
    # Pearl floats ahead
    pearl_e.location = (last_seg[1] + 4.5 + math.sin(t * 0.8) * 0.5,
                        new_y_h + math.cos(t * 0.6) * 1.0,
                        new_z_h + 1.5 + math.sin(t * 1.0) * 0.3)
    pearl_e.rotation_euler = (0, 0, t * 0.5)
    pearl_e.keyframe_insert("location", frame=f)
    pearl_e.keyframe_insert("rotation_euler", frame=f)
    # Jaw open/close (dragon chasing pearl)
    jaw_e.rotation_euler = (math.radians(25) + math.sin(t * 4.0) * math.radians(15), 0, 0)
    jaw_e.keyframe_insert("rotation_euler", frame=f)
    # Tongue flick
    tongue_e.rotation_euler = (math.sin(t * 8.0) * math.radians(15), 0, 0)
    tongue_e.keyframe_insert("rotation_euler", frame=f)

# 8 PORTERS jump rhythmically
for p in porters:
    phase = p["phase"]
    base_z = p["e"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Bounce
        p["e"].location.z = base_z + abs(math.sin(t * 2.5 + phase)) * 0.2
        p["e"].keyframe_insert("location", frame=f)
        # Head turn
        p["head"].rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(5), 0,
                                     math.sin(t * 1.2 + phase) * math.radians(15))
        p["head"].keyframe_insert("rotation_euler", frame=f)

# 4 mini dragons swim
for md in mini_dragons:
    phase = md["_phase"]
    base_x = md.location.x
    base_y = md.location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        md.rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(10),
                              math.sin(t * 0.8 + phase + 0.3) * math.radians(5),
                              t * 0.3 + phase)
        md.keyframe_insert("rotation_euler", frame=f)

# 2 LION DANCERS bounce + head shake
for ld in lion_dancers:
    phase = ld["phase"]
    base_z = ld["e"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Bounce
        ld["e"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.3
        ld["e"].rotation_euler = (0, 0, math.sin(t * 1.0 + phase) * math.radians(20))
        ld["e"].keyframe_insert("location", frame=f)
        ld["e"].keyframe_insert("rotation_euler", frame=f)
        # Head shake aggressive
        ld["head"].rotation_euler = (math.sin(t * 3.0 + phase) * math.radians(10), 0,
                                      math.sin(t * 2.5 + phase) * math.radians(25))
        ld["head"].keyframe_insert("rotation_euler", frame=f)

# 6 ACROBATS flip (rotate continuously)
for ac in acrobats:
    phase = ac["phase"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Flipping rotation
        ac["e"].rotation_euler = (t * 2.0 + phase, 0, ac["e"].rotation_euler.z + math.sin(t * 1.5) * math.radians(20))
        # Z bounce up high
        ac["e"].location.z = 1.5 + abs(math.sin(t * 1.5 + phase)) * 1.5
        ac["e"].keyframe_insert("location", frame=f)
        ac["e"].keyframe_insert("rotation_euler", frame=f)

# 4 DRUMMERS hit drums
for dr in drummers:
    phase = dr["phase"]
    base_z = dr["e"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Body bob
        dr["e"].location.z = base_z + abs(math.sin(t * 3.0 + phase)) * 0.05
        dr["e"].keyframe_insert("location", frame=f)
        # Drum pulse scale
        s = 1 + math.sin(t * 6.0 + phase) * 0.05
        dr["drum"].scale = (s, s, s)
        dr["drum"].keyframe_insert("scale", frame=f)

# 30 lanterns sway
for l in lanterns:
    phase = l["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        l.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(8),
                             math.cos(t * 1.3 + phase) * math.radians(6),
                             0)
        s = 1 + math.sin(t * 2.0 + phase) * 0.05
        l.scale = (s, s, s)
        l.keyframe_insert("rotation_euler", frame=f)
        l.keyframe_insert("scale", frame=f)

# 50 FIREWORKS bursts (expand + fade cyclically)
for fw in fireworks:
    phase = fw["_phase"]
    speed = fw["_speed"]
    for f in range(1, total_frames + 1, 2):
        t = (f - 1) / fps
        # Cyclic explosion
        cycle = (t * speed + phase) % 2.5
        if cycle < 1.0:
            s = cycle * 1.5  # expand
        else:
            s = max(0.1, 1.5 - (cycle - 1.0) * 0.5)  # fade
        fw.scale = (s, s, s)
        fw.keyframe_insert("scale", frame=f)

# 12 banners wave
for ban in banners:
    phase = ban["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        ban.rotation_euler = (0, math.sin(t * 1.0 + phase) * math.radians(4),
                               math.sin(t * 0.9 + phase) * math.radians(5))
        ban.keyframe_insert("rotation_euler", frame=f)

# 200 petals fall + tumble
for pt in petals:
    phase = pt["_phase"]; speed = pt["_speed"]
    bx, by, bz = pt["_base_x"], pt["_base_y"], pt["_base_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        z = bz - (speed * t) % 18
        x = bx + math.sin(t * 1.0 + phase) * 0.8
        y = by + math.cos(t * 0.8 + phase) * 0.8
        pt.location = (x, y, max(-0.2, z))
        pt.rotation_euler = (phase + t * 1.5, phase + t * 1.2, phase + t * 1.8)
        pt.keyframe_insert("location", frame=f)
        pt.keyframe_insert("rotation_euler", frame=f)

# 40 sparks fly up
for sp in sparks:
    phase = sp["_phase"]; speed = sp["_speed"]
    bx, by, bz = sp["_base_x"], sp["_base_y"], sp["_base_z"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        z = bz + (speed * t) % 8
        x = bx + math.sin(t * 2.0 + phase) * 0.5
        y = by + math.cos(t * 1.8 + phase) * 0.5
        s = 1 + math.sin(t * 5.0 + phase) * 0.4
        sp.location = (x, y, z)
        sp.scale = (s, s, s)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("scale", frame=f)

# Moon breathe + stars twinkle
for f in range(1, total_frames + 1, 5):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.8) * 0.04
    moon.scale = (s, s, s)
    moon.keyframe_insert("scale", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_chinese_dragon_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_chinese_dragon_new_year] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_chinese_dragon_new_year] Dragon 20-seg serpentine + head + pearl + 4 mini dragons + 8 porters + 2 lion dancers + 6 acrobats + 4 drummers + 30 lanterns + 50 fireworks + 12 banners + 3 pagodas + 200 petals + 40 sparks")
