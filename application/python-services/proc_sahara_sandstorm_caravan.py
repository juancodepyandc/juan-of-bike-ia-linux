"""
proc_sahara_sandstorm_caravan.py — 210e procédural AuroraIA (74e qualité)
Sahara sandstorm + caravane chameaux : ONE ground + 600 sand particles drift horizontal + 8 chameaux + 5 tuareg + oasis
FIXES : 1 ground propre + sand storm particles thématiques obligatoires
"""
import bpy, bmesh, math, random, os

random.seed(0x5A4A210)

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
M_SKY = mat("sky", (0.85, 0.65, 0.40, 1.0), 0.0, 0.85, emission=(0.92,0.72,0.45), emission_strength=2.0)
M_SUN_VEILED = mat("sun", (1.0, 0.75, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.78,0.32), emission_strength=12.0, alpha=0.85)
M_SAND_GROUND = mat("sand", (0.95, 0.80, 0.45, 1.0), 0.0, 0.85, emission=(0.85,0.72,0.40), emission_strength=0.5)
M_SAND_DUNE = mat("sand_d", (0.88, 0.72, 0.38, 1.0), 0.0, 0.85, emission=(0.78,0.65,0.35), emission_strength=0.4)
M_ROCK_DESERT = mat("rock", (0.55, 0.40, 0.28, 1.0), 0.0, 0.85)

# Sand particles
M_SAND_PARTICLE = mat("sand_p", (0.95, 0.78, 0.45, 1.0), 0.0, 0.55, emission=(0.95,0.78,0.45), emission_strength=3.5, alpha=0.65)

# Camel
M_CAMEL_BROWN = mat("camel_br", (0.65, 0.45, 0.25, 1.0), 0.0, 0.75, emission=(0.55,0.38,0.22), emission_strength=0.3)
M_CAMEL_LIGHT = mat("camel_l", (0.85, 0.65, 0.35, 1.0), 0.0, 0.70, emission=(0.75,0.58,0.30), emission_strength=0.3)
M_CAMEL_EYE = mat("camel_eye", (0.10, 0.08, 0.05, 1.0), 0.0, 0.20)
M_SADDLE = mat("saddle", (0.40, 0.20, 0.10, 1.0), 0.0, 0.65, emission=(0.35,0.18,0.08), emission_strength=0.3)
M_SADDLE_DECO = mat("saddle_d", (0.85, 0.15, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.18), emission_strength=0.6)
M_BLANKET = mat("blanket", (0.85, 0.25, 0.20, 1.0), 0.0, 0.65, emission=(0.78,0.25,0.20), emission_strength=0.4)

# Tuareg
M_INDIGO = mat("indigo", (0.10, 0.20, 0.55, 1.0), 0.0, 0.55, emission=(0.10,0.20,0.55), emission_strength=0.5)
M_INDIGO_LIGHT = mat("indigo_l", (0.18, 0.30, 0.70, 1.0), 0.0, 0.55, emission=(0.18,0.30,0.70), emission_strength=0.6)
M_SKIN_TUAREG = mat("skin_t", (0.55, 0.40, 0.28, 1.0), 0.0, 0.60, emission=(0.45,0.32,0.22), emission_strength=0.3)
M_ROBE_WHITE = mat("robe_w", (0.88, 0.82, 0.65, 1.0), 0.0, 0.65, emission=(0.78,0.72,0.55), emission_strength=0.4)

# Oasis
M_WATER = mat("water", (0.25, 0.55, 0.65, 0.75), 0.4, 0.10, emission=(0.30,0.60,0.70), emission_strength=1.0, alpha=0.75)
M_PALM_TRUNK = mat("palm_t", (0.45, 0.30, 0.18, 1.0), 0.0, 0.85)
M_PALM_LEAF = mat("palm_l", (0.30, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.25,0.50,0.22), emission_strength=0.4)
M_DATES = mat("dates", (0.55, 0.30, 0.15, 1.0), 0.0, 0.55, emission=(0.45,0.25,0.13), emission_strength=0.5)

# Cobra + scorpion
M_COBRA = mat("cobra", (0.55, 0.40, 0.20, 1.0), 0.3, 0.45, emission=(0.50,0.38,0.20), emission_strength=0.5)
M_COBRA_BELLY = mat("cobra_b", (0.92, 0.85, 0.55, 1.0), 0.0, 0.55, emission=(0.85,0.78,0.50), emission_strength=0.4)
M_COBRA_EYE = mat("cobra_eye", (1.0, 0.30, 0.15, 1.0), 0.0, 0.15, emission=(1.0,0.30,0.15), emission_strength=8.0)
M_SCORPION = mat("scorp", (0.25, 0.18, 0.10, 1.0), 0.4, 0.45, emission=(0.25,0.18,0.10), emission_strength=0.4)

# Vulture
M_VULTURE = mat("vulture", (0.35, 0.25, 0.20, 1.0), 0.0, 0.55, emission=(0.30,0.22,0.18), emission_strength=0.3)
M_VULTURE_HEAD = mat("vulture_h", (0.75, 0.45, 0.30, 1.0), 0.0, 0.55)
M_VULTURE_EYE = mat("v_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.15, emission=(1.0,0.85,0.20), emission_strength=5.0)

# ============ SKY + VEILED SUN ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.60))
sky.scale = (1,1,0.60)
sun = smooth_sphere("sun", r=5.5, loc=(0, 38, 22), mat_=M_SUN_VEILED)
# Halo dusty
for i in range(2):
    smooth_sphere(f"sun_halo{i}", r=5.5 + (i+1)*1.5, loc=(0, 38, 22),
                  mat_=M_SUN_VEILED)

# ============ ONE clean sand ground (single plane) ============
ground = beveled_cube("ground", (90, 90, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_SAND_GROUND)

# 50 ORGANIC DUNES (3D bumps, NOT stacked flat layers)
for i in range(50):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 40)
    dx = rad * math.cos(a)
    dy = rad * math.sin(a)
    smooth_sphere(f"dune{i}", r=random.uniform(1.5, 4.0), segs=20, rings=14,
                  loc=(dx, dy, 0), mat_=M_SAND_DUNE,
                  scale=(random.uniform(2.0, 4.0),
                         random.uniform(1.5, 3.0),
                         random.uniform(0.25, 0.55))).rotation_euler = (0, 0, random.uniform(0, math.pi*2))

# 30 rocks scattered (organic)
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 38)
    smooth_sphere(f"rock{i}", r=random.uniform(0.4, 1.2),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.2),
                  mat_=M_ROCK_DESERT,
                  scale=(random.uniform(0.8,1.4), random.uniform(0.8,1.4),
                         random.uniform(0.5,0.9))).rotation_euler = (random.uniform(-0.2, 0.2),
                                                                       random.uniform(-0.2, 0.2),
                                                                       random.uniform(0, math.pi*2))

# 4 MASSIVE BACKGROUND DUNES (huge silhouettes)
for i in range(4):
    a = (i / 4.0) * math.pi * 2
    rad = 35
    smooth_sphere(f"big_dune{i}", r=8, segs=24, rings=14,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0),
                  mat_=M_SAND_DUNE,
                  scale=(2.5, 1.8, 0.4))

# ============ OASIS (one small clean water pond + palms) ============
oasis_e = empty("oasis", loc=(-15, 15, 0))
# Single water disc
cyl("oasis_water", r=2.5, depth=0.20, segs=32,
    loc=(0, 0, 0), parent=oasis_e, mat_=M_WATER)
# Organic edge rocks (8)
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    smooth_sphere(f"oasis_rock{i}", r=random.uniform(0.30, 0.55),
                  loc=(2.7*math.cos(a), 2.7*math.sin(a), 0.15),
                  parent=oasis_e, mat_=M_ROCK_DESERT)

# 3 PALM TREES around oasis
def make_palm(name, loc, scale=1.0, lean_angle=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, lean_angle)
    # Trunk 6 segs curved
    for i in range(6):
        r1 = (0.30 - i*0.025) * scale
        r2 = (0.27 - i*0.025) * scale
        seg = smooth_cone(f"{name}_t{i}", r1=r1, r2=r2, depth=1.0*scale, segs=12,
                          loc=(0, 0, (i+0.5)*1.0*scale), parent=base, mat_=M_PALM_TRUNK)
        seg.rotation_euler = (math.radians(random.uniform(-2, 4)),
                              math.radians(random.uniform(-2, 4)), 0)
    # 7 fronds radiating top
    top_z = 6 * 1.0 * scale
    for j in range(7):
        a = (j / 7.0) * math.pi * 2
        frond_e = empty(f"{name}_fr{j}", (0, 0, top_z), parent=base)
        frond_e.rotation_euler = (math.radians(-60), 0, a)
        for k in range(5):
            seg = beveled_cube(f"{name}_fr{j}_{k}", (0.18*scale, 1.0*scale, 0.04*scale),
                               loc=(0, (k+0.5)*1.0*scale, 0), parent=frond_e, mat_=M_PALM_LEAF)
            seg.scale = (1 - k*0.15, 1, 1)
            seg.rotation_euler = (math.radians(k*5), 0, 0)
        frond_e["_phase"] = random.uniform(0, math.pi*2)
    # Date clusters (2 hanging signature)
    for j in range(2):
        a = (j / 2.0) * math.pi
        smooth_sphere(f"{name}_dates{j}", r=0.30*scale,
                      loc=(0.30*scale*math.cos(a), 0.30*scale*math.sin(a), top_z - 0.2),
                      parent=base, mat_=M_DATES, scale=(1, 1, 1.5))
    return base

palms = []
palm_pos = [(-13, 14, 0, 1.0, math.radians(5)),
            (-17, 17, 0, 1.1, math.radians(-8)),
            (-14, 18, 0, 0.95, math.radians(10))]
for i, (px, py, pz, sc, lean) in enumerate(palm_pos):
    p = make_palm(f"palm{i}", (px, py, pz), scale=sc, lean_angle=lean)
    palms.append(p)

# ============ 8 CAMELS caravan file ============
def make_camel(name, loc, two_bumps=True, has_rider=True, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    color = M_CAMEL_BROWN if random.random() < 0.5 else M_CAMEL_LIGHT
    # Body
    smooth_sphere(f"{name}_body", r=0.70*scale, segs=22, rings=14, loc=(0, 0, 1.5*scale),
                  parent=base, mat_=color, scale=(2.3, 1.0, 1.0))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.60*scale, loc=(0, 0, 1.30*scale),
                  parent=base, mat_=M_CAMEL_LIGHT, scale=(2.0, 0.9, 0.6))
    # 1 or 2 humps (signature)
    if two_bumps:
        smooth_sphere(f"{name}_hump1", r=0.55*scale, loc=(-0.5*scale, 0, 2.20*scale),
                      parent=base, mat_=color, scale=(1, 1, 1.0))
        smooth_sphere(f"{name}_hump2", r=0.55*scale, loc=(0.5*scale, 0, 2.20*scale),
                      parent=base, mat_=color, scale=(1, 1, 1.0))
    else:
        smooth_sphere(f"{name}_hump", r=0.75*scale, loc=(0, 0, 2.30*scale),
                      parent=base, mat_=color, scale=(1.3, 1, 1.1))
    # 4 LONG LEGS
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.13*scale, depth=1.7*scale, segs=12,
                loc=(x*0.55*scale, y*0.30*scale, 0.85*scale), parent=base, mat_=color)
            # Foot pad
            smooth_sphere(f"{name}_foot{x_idx}{y_idx}", r=0.16*scale, loc=(x*0.55*scale, y*0.30*scale, 0.05*scale),
                          parent=base, mat_=color, scale=(1, 1.2, 0.5))
    # LONG NECK curved (signature)
    neck_pivot = empty(f"{name}_neck_pv", (1.10*scale, 0, 1.80*scale), parent=base)
    neck_pivot.rotation_euler = (math.radians(-30), 0, 0)
    for i in range(4):
        s_e = empty(f"{name}_neck_se{i}", (0, 0.30*scale, 0), parent=neck_pivot)
        cyl(f"{name}_neck{i}", r=(0.18 - i*0.015)*scale, depth=0.30*scale, segs=12,
            loc=(0, 0, 0), parent=s_e, mat_=color).rotation_euler = (math.radians(90), 0, 0)
        neck_pivot = s_e
    # HEAD
    head_e = empty(f"{name}_head_e", (0, 0.40*scale, 0), parent=neck_pivot)
    smooth_sphere(f"{name}_h", r=0.20*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=color, scale=(1.6, 0.9, 0.85))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.13*scale, loc=(0.15*scale, 0, -0.06*scale),
                  parent=head_e, mat_=M_CAMEL_LIGHT)
    # 2 ears small
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.05*scale, r2=0.005, depth=0.10*scale, segs=8,
                    loc=(side*0.08*scale, 0.02*scale, 0.18*scale), parent=head_e, mat_=color).rotation_euler = (math.radians(-15), 0, 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale, loc=(side*0.10*scale, 0.08*scale, 0.05*scale),
                      parent=head_e, mat_=M_CAMEL_EYE)
    # Tail short with tuft
    cyl(f"{name}_tail", r=0.05*scale, depth=0.40*scale, segs=10,
        loc=(-1.30*scale, 0, 1.50*scale), parent=base, mat_=color).rotation_euler = (math.radians(-25), 0, 0)
    smooth_sphere(f"{name}_tail_tuft", r=0.10*scale, loc=(-1.45*scale, 0, 1.25*scale),
                  parent=base, mat_=M_CAMEL_BROWN)
    # SADDLE + cargo (signature caravan)
    if has_rider:
        # Saddle
        beveled_cube(f"{name}_saddle", (0.6*scale, 0.5*scale, 0.20*scale), bevel_offset=0.04,
                     loc=(-0.10*scale, 0, 2.65*scale), parent=base, mat_=M_SADDLE)
        # Red decorated blanket
        beveled_cube(f"{name}_blanket", (1.4*scale, 0.95*scale, 0.04*scale), bevel_offset=0.02,
                     loc=(-0.10*scale, 0, 2.40*scale), parent=base, mat_=M_BLANKET)
        # Saddle horn
        smooth_sphere(f"{name}_saddle_horn", r=0.08*scale, loc=(0.20*scale, 0, 2.80*scale),
                      parent=base, mat_=M_SADDLE_DECO)
        # Cargo bag side
        for side in (-1, 1):
            beveled_cube(f"{name}_cargo_{side}", (0.30*scale, 0.50*scale, 0.45*scale), bevel_offset=0.03,
                         loc=(-0.40*scale, side*0.60*scale, 2.00*scale), parent=base, mat_=M_SADDLE_DECO)
    return {"root": base, "head_e": head_e}

camels = []
# 8 camels in a line caravan (file indienne)
for i in range(8):
    cy = -10 + i * 2.5  # straight line
    cx = -2 + i * 0.5   # slight zigzag
    two_humps = i % 3 != 0  # Mix bactrian + dromedary
    has_r = i % 2 == 0  # half have riders
    sc = 1.0 if i != 0 else 1.15  # leader bigger
    c = make_camel(f"camel{i}", (cx, cy, 0), two_bumps=two_humps,
                   has_rider=has_r, scale=sc, facing=math.radians(90))
    camels.append(c)

# ============ 5 TUAREG NOMADS (some riding, some walking) ============
def make_tuareg(name, loc, on_camel=False, is_chief=False, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    z_off = 2.3 if on_camel else 0  # On camel back
    # Legs (covered by robe)
    smooth_cone(f"{name}_robe", r1=0.50*scale, r2=0.30*scale, depth=1.2*scale, segs=14,
                loc=(0, 0, (0.6 + z_off)*scale), parent=base, mat_=M_ROBE_WHITE)
    # Torso
    beveled_cube(f"{name}_torso", (0.50*scale, 0.30*scale, 0.85*scale), bevel_offset=0.05,
                 loc=(0, 0, (1.50 + z_off)*scale), parent=base,
                 mat_=M_INDIGO if is_chief else M_INDIGO_LIGHT)
    # Belt sash
    beveled_cube(f"{name}_sash", (0.55*scale, 0.34*scale, 0.08*scale),
                 loc=(0, 0, (1.20 + z_off)*scale), parent=base, mat_=M_SADDLE_DECO)
    # Head
    head_e = empty(f"{name}_head_e", (0, 0, (2.05 + z_off)*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.18*scale, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_TUAREG)
    # ONLY EYES VISIBLE (tagelmust covers face) - signature tuareg
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.15*scale, 0.03*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # TAGELMUST (turban indigo signature)
    turban_e = empty(f"{name}_turban_e", (0, 0, 0.05*scale), parent=head_e)
    # Wraps around (3 layers)
    for i in range(3):
        layer = smooth_sphere(f"{name}_turb{i}", r=0.22*scale - i*0.02*scale,
                              loc=(0, 0, 0.15 - i*0.05),
                              parent=turban_e, mat_=M_INDIGO, scale=(1, 1, 0.6))
    # Tail of turban hanging (face wrap)
    beveled_cube(f"{name}_face_wrap", (0.35*scale, 0.05*scale, 0.30*scale),
                 loc=(0, -0.10*scale, -0.05*scale), parent=head_e, mat_=M_INDIGO)
    # Long tail hanging
    beveled_cube(f"{name}_turb_tail", (0.05*scale, 0.18*scale, 0.50*scale),
                 loc=(-0.15*scale, 0.05*scale, -0.05*scale), parent=head_e, mat_=M_INDIGO)
    # 2 arms
    if on_camel:
        # Holding reins
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.28*scale, 0, (1.85 + z_off)*scale), parent=base)
            sh.rotation_euler = (math.radians(-70), 0, math.radians(side*-15))
            cyl(f"{name}_up{side_idx}", r=0.08*scale, depth=0.40*scale, segs=10,
                loc=(0, 0, -0.20*scale), parent=sh, mat_=M_INDIGO_LIGHT)
            cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.38*scale, segs=10,
                loc=(0, 0, -0.60*scale), parent=sh, mat_=M_INDIGO_LIGHT)
    else:
        for side_idx, side in enumerate((-1, 1)):
            sh = empty(f"{name}_sh{side_idx}", (side*0.28*scale, 0, (1.85)*scale), parent=base)
            sh.rotation_euler = (math.radians(-20), 0, math.radians(side*-10))
            cyl(f"{name}_up{side_idx}", r=0.08*scale, depth=0.40*scale, segs=10,
                loc=(0, 0, -0.20*scale), parent=sh, mat_=M_INDIGO_LIGHT)
            cyl(f"{name}_fa{side_idx}", r=0.07*scale, depth=0.38*scale, segs=10,
                loc=(0, 0, -0.60*scale), parent=sh, mat_=M_SKIN_TUAREG)
    return {"root": base, "head_e": head_e}

tuaregs = []
# 5 tuareg, 3 riding camels + 2 walking
tuareg_specs = [
    ("tuareg1", (-2, -10, 0), True, True, math.radians(90)),    # chief on lead camel
    ("tuareg2", (-1, -5, 0), True, False, math.radians(90)),    # rider
    ("tuareg3", (0, 0, 0), True, False, math.radians(90)),      # rider
    ("tuareg4", (1.5, 4, 0), False, False, math.radians(90)),   # walker
    ("tuareg5", (2.5, 10, 0), False, False, math.radians(90)),  # walker rear
]
for spec in tuareg_specs:
    name, loc, on_cam, chief, fac = spec
    t = make_tuareg(name, loc, on_camel=on_cam, is_chief=chief, facing=fac)
    tuaregs.append(t)

# ============ COBRA snake (signature desert) ============
cobra_e = empty("cobra", loc=(8, -5, 0))
# 8 body segments serpentine raised + 1 head with hood
cobra_segs = []
for i in range(8):
    t = i / 7.0
    cx = math.sin(t * 3) * 0.5
    cz = t * 1.5  # rises up
    seg = smooth_sphere(f"cobra_b{i}", r=0.25 - i*0.015, segs=18, rings=12,
                       loc=(cx, t * 0.3, cz + 0.1), parent=cobra_e, mat_=M_COBRA,
                       scale=(1.0, 1.6, 0.85))
    # Belly lighter
    smooth_sphere(f"cobra_bel{i}", r=0.20 - i*0.012, loc=(cx, t * 0.3, cz + 0.1 - 0.07),
                  parent=cobra_e, mat_=M_COBRA_BELLY, scale=(0.8, 1.4, 0.4))
    cobra_segs.append((seg, cx, t * 0.3, cz + 0.1, i))
# Head with HOOD (signature cobra)
cobra_head_e = empty("cobra_head_e", (0, 0.30, 1.7))
cobra_head_e.parent = cobra_e
# Skull
smooth_sphere("cobra_skull", r=0.25, segs=18, rings=12, loc=(0, 0, 0),
              parent=cobra_head_e, mat_=M_COBRA, scale=(0.9, 1.3, 0.7))
# HOOD (flared back signature)
smooth_sphere("cobra_hood", r=0.42, loc=(0, -0.10, 0.0),
              parent=cobra_head_e, mat_=M_COBRA, scale=(2.0, 0.3, 1.5))
# Eyes red émissifs
for side in (-1, 1):
    smooth_sphere(f"cobra_eye_{side}", r=0.05, loc=(side*0.10, 0.20, 0.05),
                  parent=cobra_head_e, mat_=M_COBRA_EYE)
# Fangs
for side in (-1, 1):
    smooth_cone(f"cobra_fang_{side}", r1=0.025, r2=0.005, depth=0.08, segs=6,
                loc=(side*0.05, 0.30, -0.10), parent=cobra_head_e,
                mat_=mat(f"cf{side}", (0.95,0.92,0.85,1), 0, 0.5)).rotation_euler = (math.radians(150), 0, 0)
# Forked tongue
tongue_e = empty("cobra_tongue_e", (0, 0.30, -0.05), parent=cobra_head_e)
for side in (-1, 1):
    beveled_cube(f"cobra_tongue_{side}", (0.02, 0.20, 0.02),
                 loc=(side*0.03, 0.10, 0), parent=tongue_e,
                 mat_=mat(f"ct{side}", (0.85,0.20,0.30,1), 0, 0.5,
                          emission=(0.80,0.18,0.28), emission_strength=2.0))

# ============ SCORPION (signature desert) ============
scorpion_e = empty("scorpion", loc=(12, -3, 0))
scorpion_e.rotation_euler = (0, 0, math.radians(-45))
# Body (8 segments)
for i in range(5):
    smooth_sphere(f"scorp_body{i}", r=0.15 - i*0.005, segs=14, rings=10,
                  loc=(i*0.12 - 0.30, 0, 0.10), parent=scorpion_e, mat_=M_SCORPION,
                  scale=(1.0, 1.3, 0.8))
# Head + 2 small eyes
smooth_sphere("scorp_head", r=0.16, loc=(-0.45, 0, 0.10),
              parent=scorpion_e, mat_=M_SCORPION, scale=(1.0, 0.95, 0.7))
for side in (-1, 1):
    smooth_sphere(f"scorp_eye_{side}", r=0.02, loc=(-0.55, side*0.06, 0.13),
                  parent=scorpion_e, mat_=M_COBRA_EYE)
# 2 PINCERS (chelicerae) signature scorpion
for side in (-1, 1):
    p_e = empty(f"scorp_pincer_e_{side}", (-0.65, side*0.10, 0.10), parent=scorpion_e)
    p_e.rotation_euler = (0, 0, math.radians(side*-30))
    # Arm
    cyl(f"scorp_p_arm_{side}", r=0.05, depth=0.20, segs=10,
        loc=(0, 0.10, 0), parent=p_e, mat_=M_SCORPION).rotation_euler = (math.radians(90), 0, 0)
    # 2 claws V-shape
    for inner_side in (-1, 1):
        claw = smooth_cone(f"scorp_claw_{side}_{inner_side}", r1=0.05, r2=0.01, depth=0.20, segs=8,
                          loc=(0, 0.25, 0.04*inner_side), parent=p_e, mat_=M_SCORPION).rotation_euler = (math.radians(90), 0, math.radians(inner_side*30))
# 8 LEGS (4 each side)
for side in (-1, 1):
    for li in range(4):
        cyl(f"scorp_leg_{side}_{li}", r=0.025, depth=0.18, segs=8,
            loc=(li*0.10 - 0.20, side*0.15, 0.06), parent=scorpion_e, mat_=M_SCORPION).rotation_euler = (0, math.radians(60), math.radians(side*-30))
# CURLED TAIL with stinger (signature)
tail_pivot = empty("scorp_tail_pv", (0.25, 0, 0.10), parent=scorpion_e)
for i in range(5):
    a = i * 0.5
    seg = smooth_sphere(f"scorp_tail{i}", r=0.07 - i*0.008,
                       loc=(0.12*math.cos(a), 0, 0.12*math.sin(a) + i*0.06),
                       parent=tail_pivot, mat_=M_SCORPION)
# Stinger tip
smooth_cone("scorp_stinger", r1=0.04, r2=0.005, depth=0.12, segs=8,
            loc=(0.0, 0, 0.50), parent=tail_pivot, mat_=M_SCORPION).rotation_euler = (math.radians(-30), 0, 0)

# ============ 12 DESERT VULTURES orbit ============
vultures = []
for vi in range(12):
    a = (vi / 12.0) * math.pi * 2
    rad = random.uniform(18, 28)
    vx = math.cos(a) * rad
    vy = math.sin(a) * rad
    vz = random.uniform(10, 18)
    v_e = empty(f"vulture{vi}", (vx, vy, vz))
    v_e.rotation_euler = (0, 0, a + math.pi/2)
    smooth_sphere(f"v_body{vi}", r=0.30, segs=18, rings=12, loc=(0, 0, 0),
                  parent=v_e, mat_=M_VULTURE, scale=(2.0, 0.9, 0.9))
    smooth_sphere(f"v_h{vi}", r=0.13, loc=(0.50, 0, 0.05),
                  parent=v_e, mat_=M_VULTURE_HEAD)
    smooth_cone(f"v_beak{vi}", r1=0.04, r2=0.005, depth=0.12, segs=8,
                loc=(0.62, 0, 0), parent=v_e, mat_=M_VULTURE_HEAD).rotation_euler = (math.radians(80), 0, 0)
    smooth_sphere(f"v_eye{vi}", r=0.03, loc=(0.55, -0.08, 0.08),
                  parent=v_e, mat_=M_VULTURE_EYE)
    wings = []
    for side_idx, side in enumerate((-1, 1)):
        w_e = empty(f"v_w{vi}_{side_idx}", (0, side*0.30, 0), parent=v_e)
        beveled_cube(f"v_w_in{vi}_{side_idx}", (0.8, 1.4, 0.06), bevel_offset=0.04,
                     loc=(0, side*0.7, 0), parent=w_e, mat_=M_VULTURE)
        # 4 primary
        for fi in range(4):
            beveled_cube(f"v_prim{vi}_{side_idx}_{fi}", (0.14, 0.45, 0.03),
                         loc=(0.30 - fi*0.20, side*1.5, 0), parent=w_e, mat_=M_VULTURE)
        wings.append((w_e, side))
    beveled_cube(f"v_tail{vi}", (0.12, 0.40, 0.04), loc=(-0.55, 0, 0),
                 parent=v_e, mat_=M_VULTURE)
    vultures.append({"e": v_e, "wings": wings, "phase": random.uniform(0, math.pi*2),
                     "orbit_rad": rad, "orbit_speed": random.uniform(0.3, 0.5),
                     "orbit_phase": a, "base_z": vz})

# ============================================================
# ⭐ 600 SAND PARTICLES drift horizontalement (PARTICULE THÉMATIQUE OBLIGATOIRE - sandstorm)
# ============================================================
sand_particles = []
for i in range(600):
    sx = random.uniform(-40, 40)
    sy = random.uniform(-40, 40)
    sz = random.uniform(0.5, 18)
    sp = smooth_sphere(f"sandp{i}", r=random.uniform(0.04, 0.10), segs=6, rings=5,
                      loc=(sx, sy, sz), mat_=M_SAND_PARTICLE)
    sp["_phase"] = random.uniform(0, math.pi*2)
    sp["_base_x"] = sx; sp["_base_y"] = sy; sp["_base_z"] = sz
    sp["_speed_x"] = random.uniform(8.0, 14.0)  # HORIZONTAL drift fast (signature sandstorm)
    sp["_vary_y"] = random.uniform(-0.5, 0.5)
    sp["_vary_z"] = random.uniform(-0.3, 0.3)
    sand_particles.append(sp)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Sun veiled (subtle scale)
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.8) * 0.04
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)

# 8 camels walking procession (Z bob + slight head sway)
for ci, c in enumerate(camels):
    phase = ci * 0.3
    base_z = c["root"].location.z
    base_y = c["root"].location.y
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Walk forward (caravan moves slowly)
        c["root"].location.y = base_y + t * 0.5  # slow advance
        c["root"].location.z = base_z + abs(math.sin(t * 2.0 + phase)) * 0.08
        c["root"].keyframe_insert("location", frame=f)
        # Head sway
        c["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5), 0,
                                       math.sin(t * 0.6 + phase) * math.radians(10))
        c["head_e"].keyframe_insert("rotation_euler", frame=f)

# 5 tuareg walk/ride (Z bob)
for ti, tu in enumerate(tuaregs):
    phase = ti * 0.4
    base_z = tu["root"].location.z
    base_y = tu["root"].location.y
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        tu["root"].location.y = base_y + t * 0.5  # match camels
        tu["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        tu["root"].keyframe_insert("location", frame=f)
        tu["head_e"].rotation_euler = (0, 0, math.sin(t * 0.6 + phase) * math.radians(15))
        tu["head_e"].keyframe_insert("rotation_euler", frame=f)

# Palms sway in wind
for p in palms:
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        p.rotation_euler = (p.rotation_euler.x + math.sin(t * 1.5) * 0.02,
                             math.cos(t * 1.3) * math.radians(4),
                             p.rotation_euler.z)
        p.keyframe_insert("rotation_euler", frame=f)

# Cobra body undulate + head sway
for i, (seg, sx, sy, sz, idx) in enumerate(cobra_segs):
    phase = idx * 0.4
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        new_x = sx + math.sin(t * 2.0 + phase) * 0.15
        seg.location = (new_x, sy, sz)
        seg.keyframe_insert("location", frame=f)

for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    cobra_head_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(20))
    cobra_head_e.keyframe_insert("rotation_euler", frame=f)
    tongue_e.rotation_euler = (math.sin(t * 8.0) * math.radians(20), 0, 0)
    tongue_e.keyframe_insert("rotation_euler", frame=f)

# Scorpion subtle (tail twitch)
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    tail_pivot.rotation_euler = (0, math.sin(t * 2.5) * math.radians(15), 0)
    tail_pivot.keyframe_insert("rotation_euler", frame=f)

# Vultures orbit + flap
for v in vultures:
    phase = v["phase"]
    rad = v["orbit_rad"]
    speed = v["orbit_speed"]
    base_phase = v["orbit_phase"]
    base_z = v["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        flap = math.sin(t * 1.8 + phase) * math.radians(25)
        for w_e, side in v["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 1.0 + phase) * 0.6
        v["e"].location = (x, y, z)
        v["e"].rotation_euler = (0, 0, a + math.pi/2)
        v["e"].keyframe_insert("location", frame=f)
        v["e"].keyframe_insert("rotation_euler", frame=f)

# ============================================================
# ⭐⭐⭐ 600 SAND PARTICLES DRIFT HORIZONTAL FAST (sandstorm signature)
# ============================================================
for sp in sand_particles:
    phase = sp["_phase"]
    speed_x = sp["_speed_x"]
    vary_y = sp["_vary_y"]
    vary_z = sp["_vary_z"]
    bx, by, bz = sp["_base_x"], sp["_base_y"], sp["_base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Fast horizontal drift (signature sandstorm)
        x = bx - (speed_x * t) % 80  # blow from right to left
        y = by + math.sin(t * 1.0 + phase) * vary_y
        z = bz + math.sin(t * 1.5 + phase) * vary_z
        sp.location = (x, y, z)
        sp.keyframe_insert("location", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_sahara_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_sahara_sandstorm_caravan] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_sahara_sandstorm_caravan] ONE ground sand + 50 organic dunes + 30 rocks + oasis + 3 palms + 8 camels walking + 5 tuareg + cobra hood + scorpion + 12 vultures + 600 SAND PARTICLES horizontal drift")
print("⭐ FIXES: 1 ground (no sandwich) + 600 sand horizontal drift 8-14 m/s thematic mandatory ⭐")
