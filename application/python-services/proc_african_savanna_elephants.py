"""
proc_african_savanna_elephants.py — 207e procédural AuroraIA (71e qualité)
Savane africaine : 5 éléphants + 4 girafes + 3 lions + 8 zèbres + 12 antilopes + 5 hippos + baobab + acacias + flamants + vautours
"""
import bpy, bmesh, math, random, os

random.seed(0x5A4A207)

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
M_SKY = mat("sky", (0.95, 0.55, 0.25, 1.0), 0.0, 0.7, emission=(1.0,0.60,0.28), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.65, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.70,0.25), emission_strength=20.0)
M_CLOUD = mat("cloud", (1.0, 0.78, 0.55, 1.0), 0.0, 0.55, emission=(1.0,0.78,0.55), emission_strength=2.5, alpha=0.85)
M_GROUND = mat("ground", (0.65, 0.50, 0.28, 1.0), 0.0, 0.85, emission=(0.55,0.45,0.25), emission_strength=0.4)
M_DIRT = mat("dirt", (0.45, 0.30, 0.18, 1.0), 0.0, 0.85)
M_GRASS = mat("grass", (0.78, 0.68, 0.35, 1.0), 0.0, 0.80, emission=(0.65,0.58,0.30), emission_strength=0.4)
M_WATER = mat("water", (0.25, 0.45, 0.55, 0.75), 0.4, 0.10, emission=(0.30,0.55,0.65), emission_strength=0.8, alpha=0.75)
M_MUD = mat("mud", (0.45, 0.30, 0.20, 1.0), 0.0, 0.85)

# Elephant
M_ELE_GREY = mat("ele_g", (0.55, 0.50, 0.50, 1.0), 0.0, 0.85, emission=(0.45,0.42,0.42), emission_strength=0.3)
M_ELE_BELLY = mat("ele_b", (0.70, 0.65, 0.62, 1.0), 0.0, 0.85, emission=(0.55,0.52,0.50), emission_strength=0.3)
M_TUSK = mat("tusk", (0.95, 0.92, 0.85, 1.0), 0.3, 0.40, emission=(0.88,0.85,0.78), emission_strength=0.5)
M_ELE_EYE = mat("ele_eye", (0.15, 0.10, 0.06, 1.0), 0.0, 0.20, emission=(0.20,0.15,0.10), emission_strength=0.5)

# Giraffe
M_GIRAFFE = mat("giraffe", (0.88, 0.70, 0.35, 1.0), 0.0, 0.65, emission=(0.78,0.62,0.30), emission_strength=0.4)
M_GIRAFFE_SPOT = mat("giraffe_s", (0.45, 0.25, 0.10, 1.0), 0.0, 0.75, emission=(0.38,0.20,0.08), emission_strength=0.3)
M_GIRAFFE_MANE = mat("giraffe_m", (0.35, 0.20, 0.10, 1.0), 0.0, 0.80)

# Lion
M_LION = mat("lion", (0.85, 0.65, 0.35, 1.0), 0.0, 0.65, emission=(0.75,0.58,0.30), emission_strength=0.5)
M_LION_MANE = mat("lion_m", (0.55, 0.30, 0.15, 1.0), 0.0, 0.80, emission=(0.50,0.28,0.13), emission_strength=0.5)
M_LION_BELLY = mat("lion_b", (0.92, 0.78, 0.55, 1.0), 0.0, 0.65, emission=(0.85,0.72,0.50), emission_strength=0.4)
M_LION_EYE = mat("lion_eye", (1.0, 0.85, 0.30, 1.0), 0.0, 0.15, emission=(1.0,0.85,0.30), emission_strength=8.0)

# Zebra
M_ZEBRA_WHITE = mat("zebra_w", (0.95, 0.92, 0.88, 1.0), 0.0, 0.70, emission=(0.85,0.82,0.78), emission_strength=0.4)
M_ZEBRA_BLACK = mat("zebra_b", (0.08, 0.06, 0.05, 1.0), 0.0, 0.80)

# Antelope
M_ANTELOPE = mat("antelope", (0.85, 0.55, 0.30, 1.0), 0.0, 0.65, emission=(0.78,0.50,0.28), emission_strength=0.4)
M_ANTELOPE_BELLY = mat("antelope_b", (0.95, 0.85, 0.65, 1.0), 0.0, 0.65, emission=(0.85,0.78,0.60), emission_strength=0.5)
M_ANTELOPE_HORN = mat("antelope_h", (0.30, 0.20, 0.10, 1.0), 0.4, 0.45, emission=(0.25,0.18,0.10), emission_strength=0.3)

# Hippo
M_HIPPO = mat("hippo", (0.45, 0.35, 0.30, 1.0), 0.1, 0.75, emission=(0.40,0.32,0.28), emission_strength=0.3)
M_HIPPO_BELLY = mat("hippo_b", (0.65, 0.55, 0.45, 1.0), 0.0, 0.78, emission=(0.55,0.48,0.40), emission_strength=0.3)

# Baobab
M_BAOBAB = mat("baobab", (0.55, 0.42, 0.30, 1.0), 0.0, 0.85, emission=(0.50,0.38,0.28), emission_strength=0.4)
M_BAOBAB_LEAF = mat("baobab_l", (0.40, 0.55, 0.25, 1.0), 0.0, 0.65, emission=(0.35,0.48,0.22), emission_strength=0.5)
M_BAOBAB_FRUIT = mat("baobab_f", (0.85, 0.65, 0.35, 1.0), 0.0, 0.55, emission=(0.78,0.58,0.30), emission_strength=0.6)

# Acacia
M_ACACIA_TRUNK = mat("acacia_t", (0.55, 0.40, 0.25, 1.0), 0.0, 0.85)
M_ACACIA_LEAF = mat("acacia_l", (0.65, 0.75, 0.35, 1.0), 0.0, 0.65, emission=(0.58,0.68,0.30), emission_strength=0.6)

# Flamingo
M_FLAMINGO = mat("flamingo", (0.95, 0.55, 0.65, 1.0), 0.0, 0.55, emission=(0.95,0.55,0.65), emission_strength=1.2)
M_FLAMINGO_DARK = mat("flamingo_d", (0.85, 0.35, 0.45, 1.0), 0.0, 0.55, emission=(0.80,0.30,0.40), emission_strength=1.0)
M_FLAMINGO_BEAK = mat("flamingo_beak", (0.20, 0.10, 0.05, 1.0), 0.0, 0.50)

# Vulture
M_VULTURE = mat("vulture", (0.35, 0.25, 0.20, 1.0), 0.0, 0.55, emission=(0.30,0.22,0.18), emission_strength=0.3)
M_VULTURE_HEAD = mat("vulture_h", (0.75, 0.45, 0.30, 1.0), 0.0, 0.55)
M_VULTURE_EYE = mat("vulture_eye", (1.0, 0.85, 0.20, 1.0), 0.0, 0.15, emission=(1.0,0.85,0.20), emission_strength=5.0)

# Dust
M_DUST = mat("dust", (0.85, 0.65, 0.35, 1.0), 0.0, 0.55, emission=(0.85,0.65,0.35), emission_strength=2.0, alpha=0.5)

# ============ SKY + SUN setting ============
sky = smooth_sphere("sky", r=95, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY, scale=(1,1,0.60))
sky.scale = (1,1,0.60)
# Large setting sun (low on horizon)
sun = smooth_sphere("sun", r=6.5, loc=(0, 38, 8), mat_=M_SUN)
# Sun halos (3 concentric)
for i in range(3):
    halo = smooth_sphere(f"sun_halo{i}", r=6.5 + (i+1)*2.0, loc=(0, 38, 8),
                        mat_=M_SUN, scale=(1, 1, 1))
    halo["_phase"] = i * 0.5

# 8 clouds drift
clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(22, 32)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(12, 22)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.0, 3.5),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ GROUND + WATERHOLE ============
ground = beveled_cube("ground", (70, 70, 0.4), bevel_offset=0.05, loc=(0, 0, -0.2), mat_=M_GROUND)
# Watering hole (waterhole)
waterhole_e = empty("waterhole", loc=(-10, 8, 0))
# Mud rim
smooth_sphere("waterhole_mud", r=5.0, loc=(0, 0, 0.05),
              parent=waterhole_e, mat_=M_MUD, scale=(1, 1, 0.1))
# Water surface
smooth_sphere("waterhole_water", r=4.0, segs=32, rings=18, loc=(0, 0, 0.10),
              parent=waterhole_e, mat_=M_WATER, scale=(1, 1, 0.08))

# Grass patches (30 tufts dispersed)
for i in range(30):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(8, 30)
    smooth_sphere(f"grass_p{i}", r=random.uniform(0.4, 0.8),
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_GRASS, scale=(1, 1, 0.20))

# ============ ELEPHANT constructor ============
def make_elephant(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)

    # Body massive (main barrel)
    smooth_sphere(f"{name}_body", r=1.5*scale, segs=24, rings=16, loc=(0, 0, 1.8*scale),
                  parent=base, mat_=M_ELE_GREY, scale=(2.0, 1.3, 1.1))
    # Belly lighter
    smooth_sphere(f"{name}_belly", r=1.2*scale, loc=(0, 0, 1.4*scale),
                  parent=base, mat_=M_ELE_BELLY, scale=(1.7, 1.1, 0.7))

    # 4 LEGS massive (pillar-like signature)
    leg_data = [(-0.85, -0.55), (-0.85, 0.55), (0.85, -0.55), (0.85, 0.55)]
    legs_e = []
    for li, (lx, ly) in enumerate(leg_data):
        leg_e = empty(f"{name}_leg_e{li}", (lx*scale, ly*scale, 1.6*scale), parent=base)
        legs_e.append(leg_e)
        # Upper leg (thick)
        cyl(f"{name}_leg{li}", r=0.35*scale, depth=1.4*scale, segs=14,
            loc=(0, 0, -0.7*scale), parent=leg_e, mat_=M_ELE_GREY)
        # Foot pad
        cyl(f"{name}_foot{li}", r=0.40*scale, depth=0.15*scale, segs=16,
            loc=(0, 0, -1.55*scale), parent=leg_e, mat_=M_ELE_GREY)
        # 4 toenails
        for ti in range(4):
            smooth_sphere(f"{name}_toe{li}_{ti}", r=0.06*scale,
                          loc=(0.30*scale*math.cos(ti*math.pi/2),
                               0.30*scale*math.sin(ti*math.pi/2), -1.55*scale),
                          parent=leg_e, mat_=M_TUSK)

    # Tail (thin with tuft)
    tail_e = empty(f"{name}_tail_e", (-2.2*scale, 0, 1.7*scale), parent=base)
    cyl(f"{name}_tail", r=0.08*scale, depth=1.2*scale, segs=10,
        loc=(0, 0, -0.5*scale), parent=tail_e, mat_=M_ELE_GREY)
    # Tail tuft
    smooth_sphere(f"{name}_tail_tuft", r=0.12*scale, loc=(0, 0, -1.15*scale),
                  parent=tail_e, mat_=M_GIRAFFE_MANE)

    # HEAD (signature elephant)
    head_e = empty(f"{name}_head_e", (2.0*scale, 0, 2.5*scale), parent=base)
    # Skull
    smooth_sphere(f"{name}_head", r=0.80*scale, segs=24, rings=16, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ELE_GREY, scale=(1.0, 1.4, 1.1))
    # Forehead bump
    smooth_sphere(f"{name}_forehead", r=0.55*scale, loc=(0, -0.20*scale, 0.35*scale),
                  parent=head_e, mat_=M_ELE_GREY, scale=(1, 0.7, 0.8))

    # 2 BIG EARS (signature African elephant)
    for side in (-1, 1):
        ear_e = empty(f"{name}_ear_e{side}", (side*0.85*scale, 0.10*scale, 0.30*scale), parent=head_e)
        ear_e.rotation_euler = (math.radians(15), math.radians(side*45), math.radians(side*-15))
        # Ear flat oval (large fan-shaped, signature African)
        ear = beveled_cube(f"{name}_ear{side}", (0.08*scale, 1.2*scale, 1.4*scale), bevel_offset=0.06,
                          loc=(0, 0, 0), parent=ear_e, mat_=M_ELE_GREY)
        # Inner ear lighter
        beveled_cube(f"{name}_ear_in{side}", (0.04*scale, 0.95*scale, 1.15*scale),
                     loc=(side*-0.05*scale, 0, 0), parent=ear_e, mat_=M_ELE_BELLY)

    # 2 EYES (small)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.10*scale, loc=(side*0.30*scale, -0.65*scale, 0.10*scale),
                      parent=head_e, mat_=M_ELE_EYE)

    # TRUNK (signature trompe) - 6 segments tapering down
    trunk_pivot = empty(f"{name}_trunk_pv", (0, -0.80*scale, -0.20*scale), parent=head_e)
    trunk_pivot.rotation_euler = (math.radians(20), 0, 0)
    trunk_segs_e = []
    parent_e = trunk_pivot
    for i in range(6):
        s_e = empty(f"{name}_trunk_se{i}", (0, 0.45*scale, 0), parent=parent_e)
        trunk_segs_e.append(s_e)
        r = (0.30 - i*0.035) * scale
        seg = cyl(f"{name}_trunk{i}", r=r, depth=0.45*scale, segs=14,
                 loc=(0, 0, 0), parent=s_e, mat_=M_ELE_GREY)
        seg.rotation_euler = (math.radians(90), 0, 0)
        parent_e = s_e
    # Trunk tip with nostrils
    tip_e = empty(f"{name}_trunk_tip_e", (0, 0.20*scale, 0), parent=parent_e)
    smooth_sphere(f"{name}_trunk_tip", r=0.10*scale, loc=(0, 0, 0),
                  parent=tip_e, mat_=M_ELE_GREY)
    # 2 nostrils
    for side in (-1, 1):
        smooth_sphere(f"{name}_nostril{side}", r=0.025*scale,
                      loc=(side*0.04*scale, 0.10*scale, 0),
                      parent=tip_e, mat_=mat(f"{name}_nos", (0.10,0.08,0.06,1), 0, 0.5))

    # 2 IVORY TUSKS (signature)
    for side in (-1, 1):
        tusk_e = empty(f"{name}_tusk_e{side}", (side*0.30*scale, -0.85*scale, -0.20*scale), parent=head_e)
        tusk_e.rotation_euler = (math.radians(75), 0, math.radians(side*-15))
        # Curved tusk (3 cone segs)
        for ti in range(3):
            r1 = (0.10 - ti*0.025) * scale
            r2 = (0.07 - ti*0.020) * scale
            seg = smooth_cone(f"{name}_tusk{side}_{ti}", r1=r1, r2=r2, depth=0.30*scale, segs=10,
                              loc=(0, 0, ti*0.30*scale + 0.15*scale), parent=tusk_e, mat_=M_TUSK)
            seg.rotation_euler = (math.radians(ti*5), 0, 0)

    return {"root": base, "head_e": head_e, "trunk_pivot": trunk_pivot,
            "trunk_segs": trunk_segs_e, "tail_e": tail_e, "legs_e": legs_e}

# 5 elephants positioned around savanna
elephants = []
ele_positions = [
    (-3, 5, 0, 1.3, math.radians(0)),     # large matriarch center
    (4, 8, 0, 1.1, math.radians(-30)),    # adult
    (-7, 12, 0, 1.0, math.radians(45)),   # adult
    (2, 14, 0, 0.7, math.radians(20)),    # baby
    (6, 4, 0, 0.95, math.radians(-90)),   # adult
]
for i, (ex, ey, ez, sc, fac) in enumerate(ele_positions):
    e = make_elephant(f"ele{i}", (ex, ey, ez), scale=sc, facing=fac)
    e["scale"] = sc
    elephants.append(e)

# ============ GIRAFFE constructor (tall + spotted) ============
def make_giraffe(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)

    # Body
    smooth_sphere(f"{name}_body", r=0.75*scale, segs=22, rings=14, loc=(0, 0, 3.0*scale),
                  parent=base, mat_=M_GIRAFFE, scale=(2.0, 1.0, 1.0))
    # Belly lighter
    smooth_sphere(f"{name}_belly", r=0.65*scale, loc=(0, 0, 2.7*scale),
                  parent=base, mat_=M_ANTELOPE_BELLY, scale=(1.8, 0.9, 0.6))

    # 4 LEGS very long (signature giraffe)
    leg_data = [(-0.6, -0.4), (-0.6, 0.4), (0.6, -0.4), (0.6, 0.4)]
    legs_e = []
    for li, (lx, ly) in enumerate(leg_data):
        leg_e = empty(f"{name}_leg_e{li}", (lx*scale, ly*scale, 2.5*scale), parent=base)
        legs_e.append(leg_e)
        # Upper leg
        cyl(f"{name}_leg{li}", r=0.13*scale, depth=2.5*scale, segs=12,
            loc=(0, 0, -1.25*scale), parent=leg_e, mat_=M_GIRAFFE)
        # Knee marker
        smooth_sphere(f"{name}_knee{li}", r=0.16*scale, loc=(0, 0, -2.50*scale),
                      parent=leg_e, mat_=M_GIRAFFE_SPOT)
        # Hoof
        cyl(f"{name}_hoof{li}", r=0.15*scale, depth=0.12*scale, segs=10,
            loc=(0, 0, -2.55*scale), parent=leg_e, mat_=mat(f"{name}_h{li}", (0.20,0.15,0.10,1), 0.3, 0.55))

    # Spots on body (10 spots)
    for si in range(10):
        a = random.uniform(0, math.pi*2)
        sx = random.uniform(-1.5, 1.5)*scale
        sy = math.sin(a) * 0.65 * scale
        sz = (2.8 + math.cos(a) * 0.3) * scale
        smooth_sphere(f"{name}_spot{si}", r=random.uniform(0.18, 0.25)*scale,
                      loc=(sx, sy, sz), parent=base, mat_=M_GIRAFFE_SPOT, scale=(1, 1, 0.4))

    # NECK very long (signature giraffe) - 6 segments
    neck_pivot = empty(f"{name}_neck_pv", (0.7*scale, 0, 3.5*scale), parent=base)
    neck_pivot.rotation_euler = (math.radians(-50), 0, 0)
    neck_segs_e = []
    parent_e = neck_pivot
    for i in range(6):
        s_e = empty(f"{name}_neck_se{i}", (0, 0, 0.45*scale), parent=parent_e)
        neck_segs_e.append(s_e)
        r = (0.18 - i*0.005) * scale
        seg = cyl(f"{name}_neck{i}", r=r, depth=0.45*scale, segs=14,
                 loc=(0, 0, 0), parent=s_e, mat_=M_GIRAFFE)
        # Neck spots (1 each side)
        for side in (-1, 1):
            smooth_sphere(f"{name}_neck_spot{i}_{side}", r=0.10*scale,
                          loc=(side*0.16*scale, 0, 0), parent=s_e, mat_=M_GIRAFFE_SPOT, scale=(0.5, 1, 1))
        parent_e = s_e
    # MANE (10 fur tufts along neck back) signature
    for i, s_e in enumerate(neck_segs_e):
        for j in range(2):
            smooth_sphere(f"{name}_mane{i}_{j}", r=0.06*scale,
                          loc=(0, -0.10*scale, j*0.05*scale), parent=s_e,
                          mat_=M_GIRAFFE_MANE, scale=(0.5, 1, 1.5))

    # HEAD (small with ossicones)
    head_e = empty(f"{name}_head_e", (0, 0, 0.50*scale), parent=neck_segs_e[-1])
    smooth_sphere(f"{name}_head", r=0.25*scale, segs=18, rings=12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_GIRAFFE, scale=(1.5, 0.9, 0.95))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.15*scale, loc=(0, 0.20*scale, -0.10*scale),
                  parent=head_e, mat_=M_GIRAFFE)
    # 2 OSSICONES (signature horn-like protrusions)
    for side in (-1, 1):
        cyl(f"{name}_oss{side}", r=0.04*scale, depth=0.25*scale, segs=10,
            loc=(side*0.10*scale, -0.05*scale, 0.25*scale), parent=head_e, mat_=M_GIRAFFE_SPOT)
        # Top tuft
        smooth_sphere(f"{name}_oss_tuft{side}", r=0.06*scale, loc=(side*0.10*scale, -0.05*scale, 0.40*scale),
                      parent=head_e, mat_=M_GIRAFFE_MANE)
    # 2 ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10*scale, loc=(side*0.22*scale, -0.05*scale, 0.18*scale),
                      parent=head_e, mat_=M_GIRAFFE, scale=(0.4, 1, 1.2))
    # 2 eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale, loc=(side*0.10*scale, 0.20*scale, 0.05*scale),
                      parent=head_e, mat_=M_ELE_EYE)
    # Tongue (occasional signature)
    smooth_sphere(f"{name}_tongue", r=0.05*scale, loc=(0, 0.35*scale, -0.15*scale),
                  parent=head_e, mat_=mat(f"{name}_tg", (0.55, 0.30, 0.40, 1), 0, 0.5,
                                          emission=(0.55,0.30,0.40), emission_strength=0.5))

    # Tail with tuft
    tail_e = empty(f"{name}_tail_e", (-1.6*scale, 0, 3.0*scale), parent=base)
    cyl(f"{name}_tail", r=0.04*scale, depth=0.7*scale, segs=8,
        loc=(0, 0, -0.35*scale), parent=tail_e, mat_=M_GIRAFFE)
    smooth_sphere(f"{name}_tail_tuft", r=0.10*scale, loc=(0, 0, -0.7*scale),
                  parent=tail_e, mat_=M_GIRAFFE_MANE)

    return {"root": base, "head_e": head_e, "neck_pivot": neck_pivot,
            "neck_segs": neck_segs_e, "tail_e": tail_e}

# 4 girafes
giraffes = []
giraffe_pos = [(-13, -3, 0, 1.1, math.radians(45)),
               (-15, 2, 0, 1.0, math.radians(-30)),
               (13, -5, 0, 1.15, math.radians(180)),
               (10, -8, 0, 0.95, math.radians(100))]
for i, (gx, gy, gz, sc, fac) in enumerate(giraffe_pos):
    g = make_giraffe(f"giraffe{i}", (gx, gy, gz), scale=sc, facing=fac)
    g["scale"] = sc
    giraffes.append(g)

# ============ LION constructor ============
def make_lion(name, loc, has_mane=True, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.55, segs=22, rings=14, loc=(0, 0, 1.0),
                  parent=base, mat_=M_LION, scale=(2.0, 1.0, 1.0))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.48, loc=(0, 0, 0.85),
                  parent=base, mat_=M_LION_BELLY, scale=(1.8, 0.9, 0.65))
    # 4 LEGS
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.13, depth=0.85, segs=12,
                loc=(x*0.55, y*0.40, 0.55), parent=base, mat_=M_LION)
            # Paw
            cyl(f"{name}_paw{x_idx}{y_idx}", r=0.14, depth=0.08, segs=12,
                loc=(x*0.55, y*0.40, 0.10), parent=base, mat_=M_LION)
            # 4 claws each
            for c in range(3):
                smooth_cone(f"{name}_claw{x_idx}{y_idx}_{c}", r1=0.02, r2=0.005, depth=0.06, segs=6,
                            loc=(x*0.55 + (c-1)*0.04, y*0.40 + 0.13, 0.08),
                            parent=base, mat_=M_TUSK).rotation_euler = (math.radians(60), 0, 0)
    # Tail (long with tuft)
    tail_e = empty(f"{name}_tail_e", (-1.3, 0, 1.0), parent=base)
    cyl(f"{name}_tail", r=0.05, depth=0.85, segs=10,
        loc=(0, 0, -0.40), parent=tail_e, mat_=M_LION)
    smooth_sphere(f"{name}_tail_tuft", r=0.10, loc=(0, 0, -0.85),
                  parent=tail_e, mat_=M_LION_MANE)
    # HEAD
    head_e = empty(f"{name}_head_e", (1.20, 0, 1.10), parent=base)
    smooth_sphere(f"{name}_head", r=0.30, segs=22, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_LION, scale=(1.0, 0.9, 0.9))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.15, loc=(0, 0.20, -0.10),
                  parent=head_e, mat_=M_LION_BELLY)
    # Nose
    smooth_sphere(f"{name}_nose", r=0.05, loc=(0, 0.33, -0.05),
                  parent=head_e, mat_=mat(f"{name}_n", (0.15,0.10,0.08,1), 0, 0.5))
    # 2 eyes (golden)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06, loc=(side*0.11, 0.20, 0.08),
                      parent=head_e, mat_=M_LION_EYE)
        # Slit pupil
        beveled_cube(f"{name}_pup{side}", (0.015, 0.04, 0.04), loc=(side*0.11, 0.25, 0.08),
                     parent=head_e, mat_=mat(f"{name}_p{side}", (0.05,0.05,0.05,1), 0, 0.5))
    # 2 round ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10, loc=(side*0.20, 0.05, 0.25),
                      parent=head_e, mat_=M_LION, scale=(1, 0.6, 1))
    # Whiskers (3 each side)
    for side in (-1, 1):
        for j in range(3):
            beveled_cube(f"{name}_wh{side}_{j}", (0.15, 0.005, 0.005),
                         loc=(side*0.18, 0.20, -0.05 + (j-1)*0.03),
                         parent=head_e, mat_=M_TUSK)
    # MANE (male)
    if has_mane:
        # 18 mane tufts around head
        for j in range(18):
            a = (j / 18.0) * math.pi * 2
            smooth_sphere(f"{name}_mane{j}", r=0.18,
                          loc=(0.40*math.cos(a), 0.0, 0.0 + 0.40*math.sin(a)),
                          parent=head_e, mat_=M_LION_MANE)
    return {"root": base, "head_e": head_e, "tail_e": tail_e}

# 3 lions (1 male + 2 females stalking)
lions = []
lion_pos = [(-5, -8, 0, True, math.radians(45)),    # male big
            (-3, -10, 0, False, math.radians(60)),  # female
            (-7, -9, 0, False, math.radians(30))]   # female
for i, (lx, ly, lz, hm, fac) in enumerate(lion_pos):
    l = make_lion(f"lion{i}", (lx, ly, lz), has_mane=hm, facing=fac)
    lions.append(l)

# ============ ZEBRA constructor (with stripes) ============
def make_zebra(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.55, segs=22, rings=14, loc=(0, 0, 1.4),
                  parent=base, mat_=M_ZEBRA_WHITE, scale=(2.0, 1.0, 1.0))
    # Belly
    smooth_sphere(f"{name}_belly", r=0.48, loc=(0, 0, 1.20),
                  parent=base, mat_=M_ZEBRA_WHITE, scale=(1.8, 0.9, 0.65))
    # STRIPES (8 vertical bands signature zebra)
    for si in range(8):
        sx = -1.0 + si * 0.30
        stripe = beveled_cube(f"{name}_stripe{si}", (0.18, 0.05, 0.80),
                              loc=(sx, 0.45, 1.4), parent=base, mat_=M_ZEBRA_BLACK)
        # Mirror on other side
        stripe2 = beveled_cube(f"{name}_stripe2{si}", (0.18, 0.05, 0.80),
                              loc=(sx, -0.45, 1.4), parent=base, mat_=M_ZEBRA_BLACK)
    # 4 LEGS (with banded stripes)
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.10, depth=1.0, segs=12,
                loc=(x*0.50, y*0.30, 0.70), parent=base, mat_=M_ZEBRA_WHITE)
            # Stripe bands
            for sb in range(3):
                cyl(f"{name}_leg_st_{x_idx}{y_idx}_{sb}", r=0.105, depth=0.06, segs=12,
                    loc=(x*0.50, y*0.30, 0.30 + sb*0.30), parent=base, mat_=M_ZEBRA_BLACK)
            # Hoof
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.12, depth=0.08, segs=10,
                loc=(x*0.50, y*0.30, 0.04), parent=base, mat_=M_ZEBRA_BLACK)
    # NECK
    neck_e = empty(f"{name}_neck_e", (1.0, 0, 1.5), parent=base)
    for i in range(3):
        cyl(f"{name}_neck{i}", r=0.18, depth=0.30, segs=12,
            loc=(i*0.15, 0, 0.20*i + 0.15), parent=neck_e, mat_=M_ZEBRA_WHITE)
        # Neck stripes (2 per seg)
        for sn in range(2):
            cyl(f"{name}_neck_st{i}_{sn}", r=0.19, depth=0.04, segs=12,
                loc=(i*0.15, 0, 0.20*i + sn*0.15), parent=neck_e, mat_=M_ZEBRA_BLACK).rotation_euler = (math.radians(20), 0, 0)
    # Mane (signature zebra short stripe mane)
    for i in range(6):
        cyl(f"{name}_mane{i}", r=0.025, depth=0.12, segs=8,
            loc=(0.15 + i*0.10, 0, 0.55 + i*0.10), parent=neck_e,
            mat_=M_ZEBRA_BLACK if i%2==0 else M_ZEBRA_WHITE).rotation_euler = (math.radians(-10), 0, 0)
    # Head
    head_e = empty(f"{name}_head_e", (1.65, 0, 2.0), parent=base)
    smooth_sphere(f"{name}_head", r=0.22, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ZEBRA_WHITE, scale=(1.6, 0.9, 0.9))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.15, loc=(0.20, 0, -0.06),
                  parent=head_e, mat_=M_ZEBRA_BLACK)
    # Head stripes (4)
    for hs in range(4):
        cyl(f"{name}_h_st{hs}", r=0.23, depth=0.025, segs=14,
            loc=(0.05 - hs*0.08, 0, 0), parent=head_e, mat_=M_ZEBRA_BLACK).rotation_euler = (0, math.radians(90), 0)
    # Ears
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.06, r2=0.005, depth=0.18, segs=8,
                    loc=(side*0.08, 0.05, 0.20), parent=head_e, mat_=M_ZEBRA_WHITE)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04, loc=(side*0.10, 0.12, 0.05),
                      parent=head_e, mat_=M_ELE_EYE)
    # Tail
    cyl(f"{name}_tail", r=0.04, depth=0.50, segs=8,
        loc=(-1.25, 0, 1.40), parent=base, mat_=M_ZEBRA_WHITE).rotation_euler = (math.radians(-30), 0, 0)
    smooth_sphere(f"{name}_tail_tuft", r=0.10, loc=(-1.45, 0, 1.10), parent=base, mat_=M_ZEBRA_BLACK)
    return {"root": base, "head_e": head_e}

# 8 zebras
zebras = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2 + 1.0
    rad = random.uniform(8, 14)
    zx = math.cos(a) * rad
    zy = math.sin(a) * rad + 12  # cluster more north
    zb = make_zebra(f"zebra{i}", (zx, zy, 0), facing=random.uniform(-math.pi, math.pi))
    zebras.append(zb)

# ============ ANTELOPE constructor (gazelle) ============
def make_antelope(name, loc, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.40, segs=20, rings=14, loc=(0, 0, 1.0),
                  parent=base, mat_=M_ANTELOPE, scale=(1.8, 0.9, 1.0))
    # White belly
    smooth_sphere(f"{name}_belly", r=0.36, loc=(0, 0, 0.85),
                  parent=base, mat_=M_ANTELOPE_BELLY, scale=(1.6, 0.85, 0.55))
    # 4 LEGS thin
    for x_idx, x in enumerate((-1, 1)):
        for y_idx, y in enumerate((-1, 1)):
            cyl(f"{name}_leg{x_idx}{y_idx}", r=0.06, depth=0.85, segs=10,
                loc=(x*0.35, y*0.22, 0.50), parent=base, mat_=M_ANTELOPE)
            cyl(f"{name}_hoof{x_idx}{y_idx}", r=0.08, depth=0.06, segs=10,
                loc=(x*0.35, y*0.22, 0.04), parent=base, mat_=M_ANTELOPE_HORN)
    # Neck
    neck_e = empty(f"{name}_neck_e", (0.65, 0, 1.10), parent=base)
    cyl(f"{name}_neck", r=0.10, depth=0.50, segs=12,
        loc=(0.10, 0, 0.30), parent=neck_e, mat_=M_ANTELOPE)
    # Head
    head_e = empty(f"{name}_head_e", (1.0, 0, 1.55), parent=base)
    smooth_sphere(f"{name}_head", r=0.16, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ANTELOPE, scale=(1.5, 0.85, 0.85))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.10, loc=(0.18, 0, -0.05),
                  parent=head_e, mat_=M_ANTELOPE)
    # 2 LONG CURVED HORNS (signature antelope)
    for side in (-1, 1):
        horn_e = empty(f"{name}_horn_e{side}", (side*0.06, -0.02, 0.18), parent=head_e)
        horn_e.rotation_euler = (math.radians(-30), math.radians(side*10), 0)
        # 4 segs spiral
        for hi in range(4):
            cyl(f"{name}_horn{side}_{hi}", r=0.025 - hi*0.003, depth=0.25, segs=8,
                loc=(0, 0, hi*0.25 + 0.12), parent=horn_e, mat_=M_ANTELOPE_HORN).rotation_euler = (math.radians(hi*5), math.radians(side*hi*2), 0)
    # Ears
    for side in (-1, 1):
        smooth_cone(f"{name}_ear{side}", r1=0.05, r2=0.005, depth=0.12, segs=8,
                    loc=(side*0.15, 0.04, 0.18), parent=head_e, mat_=M_ANTELOPE_BELLY).rotation_euler = (math.radians(-10), math.radians(side*15), 0)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.03, loc=(side*0.07, 0.10, 0.05),
                      parent=head_e, mat_=M_ELE_EYE)
    # Tail short
    cyl(f"{name}_tail", r=0.03, depth=0.20, segs=8,
        loc=(-0.85, 0, 0.95), parent=base, mat_=M_ANTELOPE).rotation_euler = (math.radians(-25), 0, 0)
    return {"root": base, "head_e": head_e}

# 12 antilopes
antelopes = []
for i in range(12):
    a = (i / 12.0) * math.pi * 2 + 2.0
    rad = random.uniform(10, 22)
    ax = math.cos(a) * rad
    ay = math.sin(a) * rad - 4  # cluster south
    an = make_antelope(f"antelope{i}", (ax, ay, 0), facing=random.uniform(-math.pi, math.pi))
    antelopes.append(an)

# ============ HIPPOPOTAMUS (5 bathing) ============
hippos = []
for i in range(5):
    a = (i / 5.0) * math.pi * 2
    rad = random.uniform(2, 3.5)
    hx = -10 + math.cos(a) * rad
    hy = 8 + math.sin(a) * rad
    h_e = empty(f"hippo{i}", (hx, hy, 0))
    h_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    # Body (large barrel, only top half above water)
    smooth_sphere(f"hippo_body{i}", r=0.85, segs=24, rings=16, loc=(0, 0, 0.40),
                  parent=h_e, mat_=M_HIPPO, scale=(1.7, 1.2, 0.8))
    # Head wide
    head_e = empty(f"hippo_head_e{i}", (1.5, 0, 0.45), parent=h_e)
    smooth_sphere(f"hippo_h{i}", r=0.60, segs=22, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_HIPPO, scale=(1.2, 1.3, 1.0))
    # Wide snout
    smooth_sphere(f"hippo_snout{i}", r=0.45, loc=(0.50, 0, -0.05),
                  parent=head_e, mat_=M_HIPPO_BELLY, scale=(1, 1.4, 0.7))
    # 2 nostrils
    for side in (-1, 1):
        smooth_sphere(f"hippo_nos{i}_{side}", r=0.07, loc=(0.85, side*0.15, 0.10),
                      parent=head_e, mat_=mat(f"hn{i}_{side}", (0.10,0.08,0.05,1), 0, 0.5))
    # 2 EYES on top
    for side in (-1, 1):
        smooth_sphere(f"hippo_eye{i}_{side}", r=0.10, loc=(0.15, side*0.30, 0.40),
                      parent=head_e, mat_=mat(f"hew{i}_{side}", (0.95,0.92,0.85,1), 0, 0.4))
        smooth_sphere(f"hippo_pup{i}_{side}", r=0.05, loc=(0.20, side*0.30, 0.40),
                      parent=head_e, mat_=M_ELE_EYE)
    # 2 ears
    for side in (-1, 1):
        smooth_sphere(f"hippo_ear{i}_{side}", r=0.08, loc=(-0.20, side*0.30, 0.50),
                      parent=head_e, mat_=M_HIPPO)
    # Mouth open (signature yawning hippo)
    if i == 0 or i == 3:
        # Open mouth showing teeth
        smooth_sphere(f"hippo_mouth{i}", r=0.40, loc=(0.55, 0, -0.30),
                      parent=head_e, mat_=mat(f"hm{i}", (0.55, 0.20, 0.25, 1), 0, 0.5,
                                              emission=(0.45,0.18,0.20), emission_strength=0.8),
                      scale=(1, 1.2, 0.7))
        # 4 large tusks
        for ti, (tx, ty) in enumerate([(-0.20, -0.15), (-0.20, 0.15), (0.20, -0.15), (0.20, 0.15)]):
            smooth_cone(f"hippo_tusk{i}_{ti}", r1=0.06, r2=0.005, depth=0.20, segs=8,
                        loc=(0.65 + tx, ty, -0.35), parent=head_e, mat_=M_TUSK).rotation_euler = (math.radians(150), 0, 0)
    # Splash water on top (bubbling effect)
    smooth_sphere(f"hippo_splash{i}", r=0.55, loc=(0, 0, 0.05),
                  parent=h_e, mat_=M_WATER, scale=(1.3, 1.2, 0.15))
    hippos.append({"e": h_e, "head": head_e, "phase": random.uniform(0, math.pi*2)})

# ============ BAOBAB TREE (giant signature African) ============
baobab_e = empty("baobab", loc=(18, 15, 0))
# Massive trunk (fat at bottom)
trunk = smooth_sphere("baobab_trunk", r=2.5, segs=28, rings=20, loc=(0, 0, 3),
                      parent=baobab_e, mat_=M_BAOBAB, scale=(1.4, 1.4, 1.5))
# Trunk taper (top)
trunk_top = smooth_cone("baobab_tt", r1=2.3, r2=1.2, depth=2.5, segs=24,
                        loc=(0, 0, 6.5), parent=baobab_e, mat_=M_BAOBAB)
# 5 massive thick branches (signature baobab "upside-down tree" sparse branches)
for bi in range(5):
    a = (bi / 5.0) * math.pi * 2
    branch_e = empty(f"baobab_b_e{bi}", (0, 0, 7.5), parent=baobab_e)
    branch_e.rotation_euler = (math.radians(55), 0, a)
    # 3 segments thick to thin
    for s in range(3):
        cyl(f"baobab_b{bi}_{s}", r=(0.85 - s*0.15), depth=1.5, segs=14,
            loc=(0, 0, s*1.5 + 0.75), parent=branch_e, mat_=M_BAOBAB)
    # Foliage spot at end (small - signature sparse leaves)
    smooth_sphere(f"baobab_leaf{bi}", r=1.2, loc=(0, 0, 5.0),
                  parent=branch_e, mat_=M_BAOBAB_LEAF, scale=(1, 1, 0.7))
    # 4 fruit pods
    for fi in range(4):
        smooth_sphere(f"baobab_fruit{bi}_{fi}", r=0.20, loc=(0.5*math.cos(fi*math.pi/2), 0.5*math.sin(fi*math.pi/2), 5.0),
                      parent=branch_e, mat_=M_BAOBAB_FRUIT, scale=(0.8, 0.8, 1.3))

# ============ 8 ACACIAS (umbrella trees) ============
acacias = []
acacia_pos = [(-22, -15), (-18, -18), (15, 18), (22, 12),
              (-25, 5), (25, -10), (-10, 20), (8, 22)]
for ai, (ax, ay) in enumerate(acacia_pos):
    ac_e = empty(f"acacia{ai}", (ax, ay, 0))
    # Trunk
    trunk_a = smooth_cone(f"acacia_t{ai}", r1=0.50, r2=0.30, depth=5.0, segs=14,
                          loc=(0, 0, 2.5), parent=ac_e, mat_=M_ACACIA_TRUNK)
    # Slight curve
    trunk_a.rotation_euler = (math.radians(random.uniform(-5, 5)),
                              math.radians(random.uniform(-5, 5)), 0)
    # UMBRELLA CANOPY (large flat parasol signature acacia)
    # Main flat canopy
    smooth_sphere(f"acacia_can{ai}", r=2.5, segs=24, rings=16, loc=(0, 0, 5.5),
                  parent=ac_e, mat_=M_ACACIA_LEAF, scale=(1, 1, 0.25))
    # Secondary layer for thickness
    smooth_sphere(f"acacia_can2{ai}", r=2.2, segs=20, rings=14, loc=(0, 0, 5.8),
                  parent=ac_e, mat_=M_ACACIA_LEAF, scale=(1, 1, 0.20))
    # Small leaf clusters around
    for j in range(8):
        a = (j / 8.0) * math.pi * 2
        smooth_sphere(f"acacia_cl{ai}_{j}", r=0.45,
                      loc=(2.0*math.cos(a), 2.0*math.sin(a), 5.4),
                      parent=ac_e, mat_=M_ACACIA_LEAF)
    ac_e["_phase"] = random.uniform(0, math.pi*2)
    acacias.append(ac_e)

# ============ 6 FLAMINGOS (near water) ============
flamingos = []
for fi in range(6):
    a = (fi / 6.0) * math.pi * 2 + 0.5
    rad = random.uniform(5, 6)
    fx = -10 + math.cos(a) * rad
    fy = 8 + math.sin(a) * rad
    f_e = empty(f"flamingo{fi}", (fx, fy, 0))
    f_e.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    # 1 leg standing (signature)
    cyl(f"fl_leg{fi}", r=0.04, depth=1.8, segs=10,
        loc=(0, 0, 0.9), parent=f_e, mat_=M_FLAMINGO_BEAK)
    cyl(f"fl_knee{fi}", r=0.06, depth=0.08, segs=10,
        loc=(0, 0, 0.7), parent=f_e, mat_=M_FLAMINGO_BEAK)
    # Other leg tucked up
    leg2_e = empty(f"fl_leg2_e{fi}", (0, 0.10, 0.9), parent=f_e)
    leg2_e.rotation_euler = (math.radians(110), 0, 0)
    cyl(f"fl_leg2{fi}", r=0.04, depth=0.8, segs=10,
        loc=(0, 0, -0.4), parent=leg2_e, mat_=M_FLAMINGO_BEAK)
    # Body (oval pink)
    smooth_sphere(f"fl_body{fi}", r=0.30, segs=20, rings=14, loc=(0, 0, 1.95),
                  parent=f_e, mat_=M_FLAMINGO, scale=(1.5, 1, 1.0))
    # Wings folded (slight dark tip)
    smooth_sphere(f"fl_w{fi}_l", r=0.18, loc=(-0.15, -0.10, 2.0),
                  parent=f_e, mat_=M_FLAMINGO_DARK, scale=(1.5, 0.4, 0.7))
    smooth_sphere(f"fl_w{fi}_r", r=0.18, loc=(-0.15, 0.10, 2.0),
                  parent=f_e, mat_=M_FLAMINGO_DARK, scale=(1.5, 0.4, 0.7))
    # Long S-CURVED NECK (signature flamingo)
    neck_e = empty(f"fl_neck_e{fi}", (0.20, 0, 2.10), parent=f_e)
    for ni in range(5):
        a = ni * 0.5
        nx = 0.18 * (1 - math.cos(a))
        nz = 0.18 * math.sin(a) + ni * 0.18
        cyl(f"fl_neck{fi}_{ni}", r=0.07, depth=0.20, segs=10,
            loc=(nx, 0, nz), parent=neck_e, mat_=M_FLAMINGO)
    # Head bent down
    head_e = empty(f"fl_head_e{fi}", (0.30, 0, 1.10), parent=neck_e)
    head_e.rotation_euler = (math.radians(60), 0, 0)
    smooth_sphere(f"fl_h{fi}", r=0.12, loc=(0, 0, 0),
                  parent=head_e, mat_=M_FLAMINGO, scale=(1.3, 0.9, 0.9))
    # Distinctive HOOKED BEAK pink + black tip (signature)
    smooth_cone(f"fl_beak{fi}", r1=0.06, r2=0.02, depth=0.25, segs=10,
                loc=(0.15, 0, -0.08), parent=head_e, mat_=M_FLAMINGO).rotation_euler = (math.radians(80), 0, 0)
    # Beak black tip (signature)
    smooth_sphere(f"fl_beak_tip{fi}", r=0.03, loc=(0.18, 0, -0.18),
                  parent=head_e, mat_=M_FLAMINGO_BEAK)
    # Eye
    smooth_sphere(f"fl_eye{fi}", r=0.025, loc=(0.05, 0.08, 0.05),
                  parent=head_e, mat_=M_ELE_EYE)
    flamingos.append({"e": f_e, "neck": neck_e, "head": head_e, "phase": random.uniform(0, math.pi*2)})

# ============ 30 VULTURES circling (sky scavengers) ============
vultures = []
for vi in range(30):
    a = (vi / 30.0) * math.pi * 2 + random.uniform(-0.1, 0.1)
    rad = random.uniform(15, 28)
    vx = math.cos(a) * rad
    vy = math.sin(a) * rad
    vz = random.uniform(8, 18)
    v_e = empty(f"vulture{vi}", (vx, vy, vz))
    v_e.rotation_euler = (0, 0, a + math.pi/2)
    # Body
    smooth_sphere(f"v_body{vi}", r=0.30, segs=18, rings=12, loc=(0, 0, 0),
                  parent=v_e, mat_=M_VULTURE, scale=(2.0, 0.9, 0.95))
    # Head (small with hooked beak)
    smooth_sphere(f"v_h{vi}", r=0.13, loc=(0.50, 0, 0.05),
                  parent=v_e, mat_=M_VULTURE_HEAD)
    # Hooked beak
    smooth_cone(f"v_beak{vi}", r1=0.04, r2=0.005, depth=0.12, segs=8,
                loc=(0.62, 0, 0), parent=v_e, mat_=M_VULTURE_HEAD).rotation_euler = (math.radians(80), 0, 0)
    # Eye
    smooth_sphere(f"v_eye{vi}", r=0.03, loc=(0.55, -0.08, 0.08),
                  parent=v_e, mat_=M_VULTURE_EYE)
    # WINGS HUGE (signature soaring vulture)
    wings = []
    for side_idx, side in enumerate((-1, 1)):
        w_e = empty(f"v_w{vi}_{side_idx}", (0, side*0.30, 0), parent=v_e)
        beveled_cube(f"v_w_in{vi}_{side_idx}", (0.8, 1.4, 0.06), bevel_offset=0.04,
                     loc=(0, side*0.7, 0), parent=w_e, mat_=M_VULTURE)
        # Wing tip darker
        beveled_cube(f"v_w_tip{vi}_{side_idx}", (0.6, 0.6, 0.05),
                     loc=(0, side*1.6, 0), parent=w_e, mat_=M_VULTURE_HEAD)
        # 4 primary feathers
        for fi in range(4):
            beveled_cube(f"v_prim{vi}_{side_idx}_{fi}", (0.14, 0.45, 0.03),
                         loc=(0.30 - fi*0.20, side*1.5, 0), parent=w_e, mat_=M_VULTURE)
        wings.append((w_e, side))
    # Tail
    beveled_cube(f"v_tail{vi}", (0.12, 0.40, 0.04), loc=(-0.55, 0, 0),
                 parent=v_e, mat_=M_VULTURE)
    vultures.append({"e": v_e, "wings": wings, "phase": random.uniform(0, math.pi*2),
                     "orbit_rad": rad, "orbit_speed": random.uniform(0.3, 0.6),
                     "orbit_phase": a, "base_z": vz})

# ============ 200 TALL GRASSES wave ============
grasses = []
for i in range(200):
    gx = random.uniform(-30, 30)
    gy = random.uniform(-30, 30)
    # Skip waterhole + dense animal areas
    if abs(gx + 10) < 5 and abs(gy - 8) < 5:
        continue
    g_e = empty(f"grass_t{i}", (gx, gy, 0))
    # 3 blades per tuft
    for j in range(3):
        a2 = random.uniform(0, math.pi*2)
        blade = beveled_cube(f"grass_t{i}_{j}", (0.04, 0.04, 0.7),
                             loc=(0.05*math.cos(a2), 0.05*math.sin(a2), 0.35),
                             parent=g_e, mat_=M_GRASS)
        blade.rotation_euler = (math.radians(random.uniform(-5, 5)),
                                math.radians(random.uniform(-5, 5)), 0)
    g_e["_phase"] = random.uniform(0, math.pi*2)
    grasses.append(g_e)

# ============ 50 DUST PARTICLES (sand) ============
dusts = []
for i in range(50):
    dx = random.uniform(-25, 25)
    dy = random.uniform(-25, 25)
    dz = random.uniform(1, 8)
    d = smooth_sphere(f"dust{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                     loc=(dx, dy, dz), mat_=M_DUST)
    d["_phase"] = random.uniform(0, math.pi*2)
    d["_base_x"] = dx; d["_base_y"] = dy; d["_base_z"] = dz
    d["_speed"] = random.uniform(0.3, 0.8)
    dusts.append(d)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Elephants : Z bob + trunk swing + ears flap + tail wave
for ei, el in enumerate(elephants):
    phase = ei * 0.5
    base_z = el["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        el["root"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.05
        el["root"].keyframe_insert("location", frame=f)
        # Head subtle
        el["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5), 0,
                                        math.sin(t * 0.6 + phase) * math.radians(10))
        el["head_e"].keyframe_insert("rotation_euler", frame=f)
        # Trunk swing (signature)
        el["trunk_pivot"].rotation_euler = (math.radians(20) + math.sin(t * 1.2 + phase) * math.radians(20),
                                             0,
                                             math.sin(t * 1.0 + phase) * math.radians(20))
        el["trunk_pivot"].keyframe_insert("rotation_euler", frame=f)
        # Trunk segments wave (propagated)
        for si, s_e in enumerate(el["trunk_segs"]):
            s_e.rotation_euler = (math.sin(t * 1.5 + phase + si*0.4) * math.radians(8),
                                   0,
                                   math.cos(t * 1.2 + phase + si*0.4) * math.radians(6))
            s_e.keyframe_insert("rotation_euler", frame=f)
        # Tail wave
        el["tail_e"].rotation_euler = (0, math.sin(t * 1.5 + phase) * math.radians(15),
                                        math.sin(t * 1.2 + phase) * math.radians(20))
        el["tail_e"].keyframe_insert("rotation_euler", frame=f)

# Giraffes : neck wave + head bob + tail
for gi, gir in enumerate(giraffes):
    phase = gi * 0.6
    base_z = gir["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        gir["root"].location.z = base_z + math.sin(t * 0.8 + phase) * 0.03
        gir["root"].keyframe_insert("location", frame=f)
        # Neck pivot
        gir["neck_pivot"].rotation_euler = (math.radians(-50) + math.sin(t * 0.6 + phase) * math.radians(12),
                                             0,
                                             math.sin(t * 0.4 + phase) * math.radians(8))
        gir["neck_pivot"].keyframe_insert("rotation_euler", frame=f)
        # Neck segments propagated wave
        for si, s_e in enumerate(gir["neck_segs"]):
            s_e.rotation_euler = (math.sin(t * 1.0 + phase + si*0.3) * math.radians(3),
                                   math.sin(t * 0.8 + phase + si*0.3) * math.radians(3),
                                   0)
            s_e.keyframe_insert("rotation_euler", frame=f)
        # Tail
        gir["tail_e"].rotation_euler = (0, math.sin(t * 1.5 + phase) * math.radians(20), 0)
        gir["tail_e"].keyframe_insert("rotation_euler", frame=f)

# Lions : subtle stalk + tail wave + head turn
for li, lion in enumerate(lions):
    phase = li * 0.8
    base_z = lion["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        lion["root"].location.z = base_z + math.sin(t * 1.2 + phase) * 0.03
        lion["root"].keyframe_insert("location", frame=f)
        lion["head_e"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(8), 0,
                                          math.sin(t * 0.6 + phase) * math.radians(15))
        lion["head_e"].keyframe_insert("rotation_euler", frame=f)
        lion["tail_e"].rotation_euler = (0, math.sin(t * 1.8 + phase) * math.radians(20),
                                          math.sin(t * 1.5 + phase) * math.radians(15))
        lion["tail_e"].keyframe_insert("rotation_euler", frame=f)

# Zebras : gallop trotting (Z bob + head turn)
for zi, zeb in enumerate(zebras):
    phase = zi * 0.4
    base_z = zeb["root"].location.z
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        zeb["root"].location.z = base_z + abs(math.sin(t * 3.0 + phase)) * 0.08
        zeb["root"].keyframe_insert("location", frame=f)
        zeb["head_e"].rotation_euler = (0, 0, math.sin(t * 1.5 + phase) * math.radians(12))
        zeb["head_e"].keyframe_insert("rotation_euler", frame=f)

# Antelopes : grazing + occasional alert head turn
for ai, ant in enumerate(antelopes):
    phase = ai * 0.3
    base_z = ant["root"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        ant["root"].location.z = base_z + math.sin(t * 1.5 + phase) * 0.04
        ant["root"].keyframe_insert("location", frame=f)
        ant["head_e"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(15), 0,
                                         math.sin(t * 0.8 + phase) * math.radians(20))
        ant["head_e"].keyframe_insert("rotation_euler", frame=f)

# Hippos : subtle bob + head turn
for hi, hip in enumerate(hippos):
    phase = hip["phase"]
    base_z = hip["e"].location.z
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        hip["e"].location.z = base_z + math.sin(t * 1.0 + phase) * 0.04
        hip["e"].keyframe_insert("location", frame=f)
        hip["head"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(5), 0,
                                       math.sin(t * 0.6 + phase) * math.radians(10))
        hip["head"].keyframe_insert("rotation_euler", frame=f)

# Acacia trees sway
for ac in acacias:
    phase = ac["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        ac.rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(3),
                              math.cos(t * 0.7 + phase) * math.radians(2),
                              0)
        ac.keyframe_insert("rotation_euler", frame=f)

# Flamingos : subtle leg shift + neck bend + head down to water
for fl in flamingos:
    phase = fl["phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        # Head bob (drinking from water)
        fl["head"].rotation_euler = (math.radians(60) + math.sin(t * 1.5 + phase) * math.radians(10),
                                       0,
                                       math.sin(t * 1.0 + phase) * math.radians(8))
        fl["head"].keyframe_insert("rotation_euler", frame=f)
        # Body sway
        fl["e"].rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(3), 0,
                                   fl["e"].rotation_euler.z + math.sin(t * 0.4 + phase) * math.radians(5))
        fl["e"].keyframe_insert("rotation_euler", frame=f)

# Vultures : flap wings + orbit
for v in vultures:
    phase = v["phase"]
    rad = v["orbit_rad"]
    speed = v["orbit_speed"]
    base_phase = v["orbit_phase"]
    base_z = v["base_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        flap = math.sin(t * 1.5 + phase) * math.radians(25)
        for w_e, side in v["wings"]:
            w_e.rotation_euler = (side * flap, 0, 0)
            w_e.keyframe_insert("rotation_euler", frame=f)
        # Orbit
        a = base_phase + speed * t
        x = rad * math.cos(a)
        y = rad * math.sin(a)
        z = base_z + math.sin(t * 1.0 + phase) * 0.8
        v["e"].location = (x, y, z)
        v["e"].rotation_euler = (0, 0, a + math.pi/2)
        v["e"].keyframe_insert("location", frame=f)
        v["e"].keyframe_insert("rotation_euler", frame=f)

# 200 grasses wave
for g in grasses:
    phase = g["_phase"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        g.rotation_euler = (math.sin(t * 1.5 + phase) * math.radians(12),
                             math.cos(t * 1.3 + phase) * math.radians(10),
                             0)
        g.keyframe_insert("rotation_euler", frame=f)

# 50 dust drift
for d in dusts:
    phase = d["_phase"]; speed = d["_speed"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    for f in range(1, total_frames + 1, 6):
        t = (f - 1) / fps
        x = bx + math.sin(t * speed + phase) * 1.0
        y = by + math.cos(t * speed * 0.8 + phase) * 1.0
        z = bz + (t * 0.4) % 3.0
        s = 1 + math.sin(t * 3.0 + phase) * 0.3
        d.location = (x, y, z)
        d.scale = (s, s, s)
        d.keyframe_insert("location", frame=f)
        d.keyframe_insert("scale", frame=f)

# Sun + halos breathe
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    s = 1 + math.sin(t * 0.5) * 0.05
    sun.scale = (s, s, s)
    sun.keyframe_insert("scale", frame=f)
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        if "_phase" in obj.keys():
            phase = obj["_phase"]
            for f in range(1, total_frames + 1, 6):
                t = (f - 1) / fps
                s = 1 + math.sin(t * 0.8 + phase) * 0.08
                obj.scale = (s, s, s)
                obj.keyframe_insert("scale", frame=f)

# Clouds drift
for c_e in clouds:
    phase = c_e["_phase"]
    bx, by = c_e.location.x, c_e.location.y
    for f in range(1, total_frames + 1, 8):
        t = (f - 1) / fps
        c_e.location = (bx + math.sin(t * 0.3 + phase) * 0.7,
                        by + math.cos(t * 0.25 + phase) * 0.7,
                        c_e.location.z)
        c_e.keyframe_insert("location", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_savanna_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_african_savanna_elephants] DONE → {out_glb} ({size_mb:.2f} MB)")
print("[proc_african_savanna_elephants] 5 elephants + 4 giraffes + 3 lions + 8 zebras + 12 antelopes + 5 hippos + baobab + 8 acacias + 6 flamingos + 30 vultures + 200 grasses + 50 dust + sun setting")
