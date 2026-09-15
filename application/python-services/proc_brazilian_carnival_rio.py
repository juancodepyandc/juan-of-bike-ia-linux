"""
proc_brazilian_carnival_rio.py — 234e procédural AuroraIA (98e qualité)
Rio Carnival: ONE pavement + carnival float + 6 samba dancers + male dancer + 4 percussionists + 4 capoeiristas + Christ Redeemer + Sugarloaf + Copacabana + 800 confetti + 400 samba sparkles
FIXES : 1 ground + 800 confetti + 400 sparkles signature Rio Carnival
"""
import bpy, bmesh, math, random, os

random.seed(0x21071C234)

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

# Rio sunset palette
M_SKY = mat("sky", (0.95, 0.55, 0.30, 1.0), 0.0, 0.7, emission=(0.92,0.52,0.28), emission_strength=2.8)
M_SUN = mat("sun", (1.0, 0.62, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.62,0.20), emission_strength=22.0)
M_CLOUD = mat("cloud", (1.0, 0.75, 0.55, 1.0), 0.0, 0.55, emission=(0.95,0.72,0.52), emission_strength=2.0, alpha=0.85)

# Pavement
M_GROUND = mat("ground", (0.42, 0.38, 0.35, 1.0), 0.0, 0.85, emission=(0.38,0.35,0.32), emission_strength=0.4)
M_PAVEMENT = mat("pave", (0.65, 0.55, 0.45, 1.0), 0.0, 0.80, emission=(0.60,0.50,0.42), emission_strength=0.5)
M_COPA_WAVE_B = mat("copa_b", (0.10, 0.10, 0.15, 1.0), 0.0, 0.80, emission=(0.10,0.10,0.15), emission_strength=0.5)
M_COPA_WAVE_W = mat("copa_w", (0.92, 0.88, 0.82, 1.0), 0.0, 0.65, emission=(0.85,0.82,0.75), emission_strength=0.5)
M_SAND_COPA = mat("sand_c", (0.92, 0.78, 0.55, 1.0), 0.0, 0.85, emission=(0.85,0.72,0.50), emission_strength=0.5)
M_OCEAN = mat("ocean", (0.20, 0.45, 0.65, 0.85), 0.4, 0.10, emission=(0.18,0.42,0.60), emission_strength=1.2, alpha=0.85)
M_OCEAN_FOAM = mat("ocean_f", (0.95, 0.98, 1.0, 1.0), 0.0, 0.20, emission=(0.92,0.95,0.98), emission_strength=2.5)

# Mountains
M_MOUNTAIN_RIO = mat("mountain_rio", (0.42, 0.38, 0.35, 1.0), 0.0, 0.85)
M_MOUNTAIN_GREEN = mat("mountain_g", (0.30, 0.45, 0.25, 1.0), 0.0, 0.75, emission=(0.28,0.42,0.22), emission_strength=0.3)

# Christ Redeemer (signature white statue)
M_CHRIST = mat("christ", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.92,0.88,0.85), emission_strength=1.2)
M_CHRIST_ROBE = mat("christ_r", (0.92, 0.88, 0.85, 1.0), 0.0, 0.60, emission=(0.88,0.85,0.82), emission_strength=1.0)

# Carnival float (signature gigantic)
M_FLOAT_BASE = mat("float_b", (0.78, 0.18, 0.18, 1.0), 0.0, 0.50, emission=(0.72,0.18,0.18), emission_strength=0.7)
M_FLOAT_RED = mat("float_r", (1.0, 0.20, 0.30, 1.0), 0.0, 0.45, emission=(0.95,0.20,0.28), emission_strength=1.0)
M_FLOAT_YELLOW = mat("float_y", (1.0, 0.85, 0.20, 1.0), 0.5, 0.30, emission=(1.0,0.85,0.20), emission_strength=1.5)
M_FLOAT_GOLD = mat("float_g", (0.95, 0.78, 0.30, 1.0), 0.95, 0.18, emission=(0.92,0.75,0.28), emission_strength=1.2)
M_FLOAT_GREEN = mat("float_gr", (0.30, 0.78, 0.30, 1.0), 0.0, 0.45, emission=(0.28,0.72,0.28), emission_strength=1.0)
M_FLOAT_BLUE = mat("float_bl", (0.20, 0.45, 0.95, 1.0), 0.0, 0.45, emission=(0.20,0.42,0.90), emission_strength=1.0)
M_FLOAT_PINK = mat("float_pk", (1.0, 0.40, 0.85, 1.0), 0.0, 0.45, emission=(0.95,0.38,0.80), emission_strength=1.0)
M_FLOAT_PURPLE = mat("float_pu", (0.75, 0.20, 0.95, 1.0), 0.0, 0.45, emission=(0.70,0.20,0.90), emission_strength=1.0)

# Dragon
M_DRAGON_BODY = mat("dragon_b", (0.30, 0.65, 0.30, 1.0), 0.4, 0.40, emission=(0.28,0.60,0.28), emission_strength=0.8)
M_DRAGON_RED = mat("dragon_r", (0.95, 0.20, 0.20, 1.0), 0.5, 0.35, emission=(0.90,0.20,0.20), emission_strength=1.0)
M_DRAGON_EYE = mat("dragon_e", (1.0, 0.20, 0.10, 1.0), 0.0, 0.10, emission=(1.0,0.20,0.10), emission_strength=12.0)

# Dancers
M_SKIN_BRAZILIAN = mat("skin", (0.85, 0.62, 0.45, 1.0), 0.0, 0.55, emission=(0.78,0.58,0.42), emission_strength=0.4)
M_SKIN_DARK = mat("skin_d", (0.55, 0.35, 0.22, 1.0), 0.0, 0.55, emission=(0.50,0.32,0.20), emission_strength=0.4)
M_BIKINI_RED = mat("bik_r", (0.95, 0.20, 0.25, 1.0), 0.3, 0.30, emission=(0.90,0.20,0.22), emission_strength=1.5)
M_BIKINI_GOLD = mat("bik_g", (0.95, 0.78, 0.30, 1.0), 0.85, 0.20, emission=(0.92,0.75,0.28), emission_strength=1.8)
M_BIKINI_GREEN = mat("bik_gr", (0.30, 0.95, 0.40, 1.0), 0.3, 0.30, emission=(0.28,0.90,0.38), emission_strength=1.6)
M_BIKINI_BLUE = mat("bik_b", (0.30, 0.55, 1.0, 1.0), 0.3, 0.30, emission=(0.28,0.50,0.95), emission_strength=1.6)
M_BIKINI_PINK = mat("bik_pk", (1.0, 0.40, 0.85, 1.0), 0.3, 0.30, emission=(0.95,0.38,0.80), emission_strength=1.5)
M_BIKINI_PURPLE = mat("bik_pu", (0.75, 0.20, 0.95, 1.0), 0.3, 0.30, emission=(0.70,0.20,0.90), emission_strength=1.5)
M_SEQUIN = mat("sequin", (1.0, 0.85, 0.30, 1.0), 0.95, 0.15, emission=(0.95,0.80,0.28), emission_strength=2.5)

# Plumage signature feathers (massive)
M_PLUME_RED = mat("p_r", (1.0, 0.20, 0.25, 1.0), 0.0, 0.40, emission=(0.95,0.20,0.22), emission_strength=2.0)
M_PLUME_GOLD = mat("p_g", (1.0, 0.85, 0.25, 1.0), 0.7, 0.20, emission=(0.95,0.80,0.25), emission_strength=2.5)
M_PLUME_GREEN = mat("p_gr", (0.30, 0.95, 0.40, 1.0), 0.0, 0.40, emission=(0.28,0.90,0.38), emission_strength=2.2)
M_PLUME_BLUE = mat("p_b", (0.30, 0.55, 1.0, 1.0), 0.0, 0.40, emission=(0.28,0.50,0.95), emission_strength=2.2)
M_PLUME_PINK = mat("p_pk", (1.0, 0.40, 0.85, 1.0), 0.0, 0.40, emission=(0.95,0.38,0.80), emission_strength=2.0)
M_PLUME_PURPLE = mat("p_pu", (0.85, 0.30, 1.0, 1.0), 0.0, 0.40, emission=(0.80,0.28,0.95), emission_strength=2.0)
M_PLUME_WHITE = mat("p_w", (1.0, 0.95, 0.92, 1.0), 0.0, 0.40, emission=(1.0,0.92,0.88), emission_strength=1.8)
M_HAIR_BLACK_B = mat("hair_b", (0.08, 0.05, 0.04, 1.0), 0.0, 0.85)
M_HAIR_BROWN_B = mat("hair_br", (0.40, 0.22, 0.10, 1.0), 0.0, 0.80)

# Capoeira white pants
M_CAPO_WHITE = mat("capo_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70, emission=(0.88,0.85,0.78), emission_strength=0.5)
M_CAPO_RED_BELT = mat("capo_rb", (0.85, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.78,0.18,0.18), emission_strength=0.7)
M_CAPO_GREEN_BELT = mat("capo_gb", (0.30, 0.65, 0.30, 1.0), 0.0, 0.55, emission=(0.28,0.60,0.28), emission_strength=0.6)
M_CAPO_BLUE_BELT = mat("capo_bb", (0.20, 0.45, 0.78, 1.0), 0.0, 0.55, emission=(0.18,0.42,0.72), emission_strength=0.6)

# Percussion drums
M_DRUM_RED = mat("drum_r", (0.78, 0.18, 0.18, 1.0), 0.0, 0.55, emission=(0.72,0.18,0.18), emission_strength=0.6)
M_DRUM_GOLD = mat("drum_g", (0.95, 0.78, 0.30, 1.0), 0.85, 0.25, emission=(0.92,0.75,0.28), emission_strength=0.9)
M_DRUM_SKIN = mat("drum_sk", (0.92, 0.85, 0.75, 1.0), 0.0, 0.55, emission=(0.85,0.80,0.72), emission_strength=0.4)
M_DRUM_BLACK = mat("drum_bk", (0.10, 0.08, 0.06, 1.0), 0.0, 0.80)

# Brazil flag colors
M_FLAG_BR_GREEN = mat("flag_brg", (0.18, 0.55, 0.30, 1.0), 0.0, 0.55, emission=(0.18,0.50,0.28), emission_strength=0.7)
M_FLAG_BR_YELLOW = mat("flag_bry", (1.0, 0.85, 0.20, 1.0), 0.5, 0.40, emission=(1.0,0.85,0.20), emission_strength=1.0)
M_FLAG_BR_BLUE = mat("flag_brb", (0.10, 0.30, 0.70, 1.0), 0.3, 0.45, emission=(0.10,0.30,0.65), emission_strength=0.8)
M_FLAG_BR_WHITE = mat("flag_brw", (0.95, 0.92, 0.88, 1.0), 0.0, 0.55, emission=(0.88,0.85,0.82), emission_strength=0.6)

# Lanterns
M_LANT_FEST = mat("lant_f", (1.0, 0.78, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.78,0.30), emission_strength=18.0)
M_LANT_RED = mat("lant_r", (1.0, 0.30, 0.30, 1.0), 0.0, 0.20, emission=(1.0,0.30,0.30), emission_strength=16.0)
M_LANT_GREEN = mat("lant_g", (0.30, 1.0, 0.40, 1.0), 0.0, 0.20, emission=(0.30,1.0,0.40), emission_strength=16.0)
M_LANT_BLUE = mat("lant_b", (0.30, 0.55, 1.0, 1.0), 0.0, 0.20, emission=(0.30,0.55,1.0), emission_strength=16.0)
M_LANT_PINK = mat("lant_pk", (1.0, 0.45, 0.85, 1.0), 0.0, 0.20, emission=(1.0,0.45,0.85), emission_strength=15.0)

# Confetti (signature multicolor)
M_CONF_R = mat("conf_r", (1.0, 0.20, 0.30, 1.0), 0.0, 0.30, emission=(0.95,0.20,0.28), emission_strength=3.0)
M_CONF_G = mat("conf_g", (0.20, 1.0, 0.30, 1.0), 0.0, 0.30, emission=(0.20,0.95,0.28), emission_strength=3.0)
M_CONF_B = mat("conf_b", (0.20, 0.55, 1.0, 1.0), 0.0, 0.30, emission=(0.20,0.50,0.95), emission_strength=3.0)
M_CONF_Y = mat("conf_y", (1.0, 0.92, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.90,0.20), emission_strength=3.2)
M_CONF_PK = mat("conf_pk", (1.0, 0.45, 0.85, 1.0), 0.0, 0.30, emission=(1.0,0.45,0.85), emission_strength=3.0)
M_CONF_PU = mat("conf_pu", (0.75, 0.20, 0.95, 1.0), 0.0, 0.30, emission=(0.70,0.20,0.90), emission_strength=3.0)
M_CONF_O = mat("conf_o", (1.0, 0.55, 0.20, 1.0), 0.0, 0.30, emission=(1.0,0.55,0.20), emission_strength=3.0)

# Samba sparkles
M_SPARK_G = mat("sp_g", (1.0, 0.85, 0.30, 1.0), 0.0, 0.10, emission=(1.0,0.85,0.30), emission_strength=22.0)
M_SPARK_A = mat("sp_a", (1.0, 0.65, 0.20, 1.0), 0.0, 0.10, emission=(1.0,0.65,0.20), emission_strength=20.0)
M_SPARK_W = mat("sp_w", (1.0, 1.0, 0.92, 1.0), 0.0, 0.10, emission=(1.0,1.0,0.92), emission_strength=24.0)

# ============ SKY + SUN + CLOUDS ============
sky = smooth_sphere("sky", r=140, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY)
sky.scale = (1,1,0.55)
sun_e = empty("sun_e", (30, 50, 18))
smooth_sphere("sun", r=6.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
for i in range(3):
    smooth_sphere(f"sun_halo{i}", r=6.0 + (i+1)*2.0, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

clouds = []
for i in range(8):
    a = (i / 8.0) * math.pi * 2
    rad = random.uniform(32, 48)
    cx, cy = rad*math.cos(a), rad*math.sin(a)
    cz = random.uniform(22, 32)
    c_e = empty(f"cloud_e{i}", (cx, cy, cz))
    for j in range(5):
        smooth_sphere(f"cloud{i}_{j}", r=random.uniform(2.5, 4.0),
                      loc=(random.uniform(-3,3), random.uniform(-2,2), random.uniform(-0.5,0.5)),
                      parent=c_e, mat_=M_CLOUD)
    c_e["_phase"] = random.uniform(0, math.pi*2)
    clouds.append(c_e)

# ============ SUGARLOAF MOUNTAIN + CORCOVADO with CHRIST REDEEMER ============
# Sugarloaf
sugar_e = empty("sugarloaf", loc=(-30, 35, 0))
smooth_cone("sugar_main", r1=10, r2=4, depth=20, segs=16,
            loc=(0, 0, 10), parent=sugar_e, mat_=M_MOUNTAIN_RIO)
smooth_sphere("sugar_top", r=5, segs=20, rings=14, loc=(0, 0, 19),
              parent=sugar_e, mat_=M_MOUNTAIN_RIO, scale=(1, 0.9, 0.6))

# Corcovado mountain
corc_e = empty("corcovado", loc=(30, 35, 0))
smooth_cone("corc_main", r1=12, r2=2, depth=20, segs=16,
            loc=(0, 0, 10), parent=corc_e, mat_=M_MOUNTAIN_GREEN)
# Christ Redeemer (signature)
christ_e = empty("christ", loc=(30, 35, 19))
# Pedestal
beveled_cube("christ_ped", (2, 2, 3), bevel_offset=0.06, loc=(0, 0, 1.5),
             parent=christ_e, mat_=M_CHRIST)
# Body
beveled_cube("christ_body", (1.5, 0.8, 3.5), bevel_offset=0.10, loc=(0, 0, 5),
             parent=christ_e, mat_=M_CHRIST_ROBE)
# Head
smooth_sphere("christ_head", r=0.50, loc=(0, 0, 7.0), parent=christ_e, mat_=M_CHRIST)
# Hair
smooth_sphere("christ_hair", r=0.55, loc=(0, 0.05, 7.05),
              parent=christ_e, mat_=M_CHRIST, scale=(1, 1, 0.85))
# Beard
smooth_sphere("christ_beard", r=0.35, loc=(0, -0.30, 6.65),
              parent=christ_e, mat_=M_CHRIST, scale=(1, 0.8, 1.2))
# OUTSTRETCHED ARMS (signature - 28m wingspan)
for side in (-1, 1):
    arm_e = empty(f"christ_a{side}", (side*0.7, 0, 6.0), parent=christ_e)
    arm_e.rotation_euler = (0, 0, math.radians(side*90))
    # Long horizontal arm (3.5m each)
    beveled_cube(f"christ_arm_main{side}", (3.5, 0.45, 0.45), bevel_offset=0.05,
                 loc=(1.75, 0, 0), parent=arm_e, mat_=M_CHRIST_ROBE)
    # Hand
    smooth_sphere(f"christ_hand{side}", r=0.30, loc=(3.6, 0, 0),
                  parent=arm_e, mat_=M_CHRIST)
# Long robe drape
smooth_cone("christ_robe", r1=0.9, r2=0.6, depth=2.0, loc=(0, 0, 2.5),
            parent=christ_e, mat_=M_CHRIST_ROBE)
# Glowing halo
for hi in range(3):
    smooth_sphere(f"christ_halo{hi}", r=0.50 + (hi+1)*0.20, loc=(0, 0, 7.0),
                  parent=christ_e, mat_=M_CHRIST)

# ============ ONE clean pavement ground ============
ground = beveled_cube("ground", (100, 100, 0.5), bevel_offset=0.08, loc=(0, 0, -0.25), mat_=M_GROUND)
# Copacabana wave pattern (signature black-white)
plaza_e = empty("plaza", (0, 0, 0))
# Wave tiles
for tx in range(60):
    for ty in range(20):
        plat_x = (tx - 29.5) * 1.3
        plat_y = -15 + ty * 0.6
        if abs(plat_y + 12) > 5: continue
        wave_offset = math.sin(plat_x * 0.4) > 0
        col = M_COPA_WAVE_B if (tx + ty + (1 if wave_offset else 0)) % 2 == 0 else M_COPA_WAVE_W
        beveled_cube(f"wave_{tx}_{ty}", (1.25, 0.55, 0.05), bevel_offset=0.01,
                     loc=(plat_x, plat_y, 0.05), parent=plaza_e, mat_=col)

# Pavement around (organic 3D)
for i in range(80):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(5, 40)
    smooth_sphere(f"pave_t{i}", r=random.uniform(0.30, 0.50), segs=14, rings=10,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_PAVEMENT if i % 2 == 0 else M_GROUND,
                  scale=(1.3, 1.2, 0.18))

# Ocean (Copacabana beach signature)
beveled_cube("ocean_main", (50, 15, 0.20), bevel_offset=0.05, loc=(0, -22, -0.05), mat_=M_OCEAN)
# Foam waves
for i in range(15):
    smooth_sphere(f"ocean_f{i}", r=random.uniform(0.30, 0.55),
                  loc=(random.uniform(-22, 22), -15, 0.05),
                  mat_=M_OCEAN_FOAM, scale=(2, 1.3, 0.15))
# Sand beach (signature golden)
beveled_cube("sand_beach", (50, 4, 0.20), bevel_offset=0.05, loc=(0, -14, 0), mat_=M_SAND_COPA)

# ============ MASSIVE CARNIVAL FLOAT (signature) ============
float_e = empty("float", loc=(0, 8, 0))
# Base wheels platform
beveled_cube("fl_base", (8, 4, 1.0), bevel_offset=0.08, loc=(0, 0, 0.5),
             parent=float_e, mat_=M_FLOAT_BASE)
# 4 wheels
for x in (-1, 1):
    for y in (-1, 1):
        cyl(f"fl_wheel{x}{y}", r=0.50, depth=0.40, segs=20,
            loc=(x*3.5, y*1.5, 0.5), parent=float_e, mat_=M_DRUM_BLACK).rotation_euler = (0, 0, math.radians(90))
# Decorative side panels
for side in (-1, 1):
    beveled_cube(f"fl_panel_{side}", (7.5, 0.10, 1.5), bevel_offset=0.05,
                 loc=(0, side*1.95, 1.5), parent=float_e, mat_=M_FLOAT_RED)
    # Gold patterns
    for pi in range(7):
        beveled_cube(f"fl_p_{side}_{pi}", (0.30, 0.05, 0.80), bevel_offset=0.02,
                     loc=((pi - 3) * 1.0, side*2.0, 1.5), parent=float_e, mat_=M_FLOAT_GOLD)
# Front shield
beveled_cube("fl_front", (0.20, 4, 2.5), bevel_offset=0.06, loc=(4, 0, 2.25),
             parent=float_e, mat_=M_FLOAT_GOLD)
# Decorative star front
for st in range(8):
    sta = (st / 8.0) * math.pi * 2
    beveled_cube(f"fl_star{st}", (0.10, 0.5, 0.15), bevel_offset=0.02,
                 loc=(4.1, math.cos(sta)*0.8, 2.5 + math.sin(sta)*0.8),
                 parent=float_e, mat_=M_FLOAT_YELLOW).rotation_euler = (sta, 0, 0)
# DRAGON SCULPTURE on float (signature serpent)
dragon_e = empty("dragon", (0, 0, 2.0), parent=float_e)
# Dragon serpentine body
dragon_segs = 12
for ds in range(dragon_segs):
    t_param = ds / float(dragon_segs - 1)
    sx_d = -t_param * 4.0 + 2.0
    sy_d = math.sin(t_param * math.pi * 2) * 1.5
    sz_d = 1.5 + math.sin(t_param * math.pi * 3) * 0.8
    sr_d = 0.45 - ds * 0.025
    smooth_sphere(f"dr_seg{ds}", r=sr_d, segs=18, rings=12,
                  loc=(sx_d, sy_d, sz_d), parent=dragon_e, mat_=M_DRAGON_BODY,
                  scale=(1.3, 1, 0.9))
    # Spines on back
    if ds % 2 == 0:
        smooth_cone(f"dr_spine{ds}", r1=0.10, r2=0.01, depth=0.25, segs=8,
                    loc=(sx_d, sy_d, sz_d + sr_d + 0.12), parent=dragon_e, mat_=M_DRAGON_RED)
# Dragon head
dr_head_e = empty("dr_he", (2.0, 0, 2.0), parent=dragon_e)
smooth_sphere("dr_head", r=0.55, segs=22, rings=16, loc=(0, 0, 0),
              parent=dr_head_e, mat_=M_DRAGON_BODY, scale=(1.5, 1, 0.9))
smooth_cone("dr_snout", r1=0.30, r2=0.15, depth=0.45, segs=14,
            loc=(0.75, 0, -0.05), parent=dr_head_e,
            mat_=M_DRAGON_BODY).rotation_euler = (0, math.radians(90), 0)
for side in (-1, 1):
    smooth_sphere(f"dr_eye{side}", r=0.10, loc=(0.30, side*0.20, 0.18),
                  parent=dr_head_e, mat_=M_DRAGON_EYE)
# Fangs
for side in (-1, 1):
    smooth_cone(f"dr_fang{side}", r1=0.05, r2=0.005, depth=0.18, segs=8,
                loc=(0.85, side*0.10, -0.10), parent=dr_head_e,
                mat_=M_CAPO_WHITE).rotation_euler = (0, math.radians(60), 0)
# Decorative side throne for queen samba dancer
beveled_cube("fl_throne", (1.5, 1.5, 0.8), bevel_offset=0.06, loc=(-2.5, 0, 1.5),
             parent=float_e, mat_=M_FLOAT_GOLD)
# Steps decoration
for sti in range(3):
    beveled_cube(f"fl_step{sti}", (3, 0.5, 0.20), bevel_offset=0.03,
                 loc=(-3, -2 - sti*0.5, 1.0 + sti*0.20), parent=float_e, mat_=M_FLOAT_PURPLE)

# ============ 6 SAMBA DANCERS with MASSIVE PLUMAGE (signature) ============
def make_samba_dancer(name, loc, bikini_mat, plume_color, is_queen=False, facing=0, scale=1.0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Legs (long signature)
    for side_idx, side in enumerate((-1, 1)):
        hip = empty(f"{name}_hip{side_idx}", (side*0.12*scale, 0, 0.85*scale), parent=base)
        leg_rx = math.radians(15 if side_idx == 0 else -15)
        hip.rotation_euler = (leg_rx, 0, 0)
        cyl(f"{name}_thigh{side_idx}", r=0.10*scale, depth=0.55*scale, segs=12,
            loc=(0, 0, -0.28*scale), parent=hip, mat_=M_SKIN_BRAZILIAN)
        cyl(f"{name}_calf{side_idx}", r=0.08*scale, depth=0.55*scale, segs=12,
            loc=(0, 0, -0.85*scale), parent=hip, mat_=M_SKIN_BRAZILIAN)
        # High heels
        beveled_cube(f"{name}_heel{side_idx}", (0.10*scale, 0.25*scale, 0.06*scale), bevel_offset=0.02,
                     loc=(0, 0.04*scale, -1.13*scale), parent=hip, mat_=M_BIKINI_GOLD)
        # Heel pin
        cyl(f"{name}_pin{side_idx}", r=0.02*scale, depth=0.12*scale, segs=8,
            loc=(0, -0.08*scale, -1.20*scale), parent=hip, mat_=M_BIKINI_GOLD)
    # Bikini bottom + sequins fringes
    cyl(f"{name}_bottom", r=0.32*scale, depth=0.18*scale, segs=18,
        loc=(0, 0, 1.0*scale), parent=base, mat_=bikini_mat)
    # Sequin fringes hanging (signature)
    for fr in range(20):
        fra = (fr / 20.0) * math.pi * 2
        for sk in range(3):
            sk_z = sk * 0.10
            beveled_cube(f"{name}_fringe{fr}_{sk}", (0.04*scale, 0.04*scale, 0.30*scale), bevel_offset=0.005,
                         loc=(0.30*scale*math.cos(fra), 0.30*scale*math.sin(fra), 0.85*scale - sk_z),
                         parent=base, mat_=M_SEQUIN)
    # Belt with sequins
    cyl(f"{name}_belt", r=0.32*scale, depth=0.06*scale, segs=18,
        loc=(0, 0, 1.15*scale), parent=base, mat_=M_FLOAT_GOLD)
    # Sequin discs
    for di in range(12):
        da = (di / 12.0) * math.pi * 2
        smooth_sphere(f"{name}_seqd{di}", r=0.04*scale,
                      loc=(0.34*scale*math.cos(da), 0.34*scale*math.sin(da), 1.15*scale),
                      parent=base, mat_=M_SEQUIN)
    # Bare midriff
    smooth_sphere(f"{name}_midriff", r=0.22*scale, loc=(0, 0, 1.40*scale),
                  parent=base, mat_=M_SKIN_BRAZILIAN, scale=(1.3, 1, 1))
    # Bikini top + sequins
    for side in (-1, 1):
        cyl(f"{name}_top{side}", r=0.13*scale, depth=0.06*scale, segs=14,
            loc=(side*0.10*scale, -0.15*scale, 1.70*scale), parent=base, mat_=bikini_mat).rotation_euler = (math.radians(90), 0, 0)
        # Sequin star on each cup
        smooth_sphere(f"{name}_top_seq{side}", r=0.05*scale, loc=(side*0.10*scale, -0.20*scale, 1.70*scale),
                      parent=base, mat_=M_SEQUIN)
    # Strap
    beveled_cube(f"{name}_strap", (0.30*scale, 0.04*scale, 0.04*scale), bevel_offset=0.01,
                 loc=(0, -0.15*scale, 1.85*scale), parent=base, mat_=bikini_mat)
    # Shoulders + arms
    cyl(f"{name}_neck", r=0.08*scale, depth=0.16*scale, segs=10,
        loc=(0, 0, 2.0*scale), parent=base, mat_=M_SKIN_BRAZILIAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 2.18*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.17*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_BRAZILIAN)
    # Hair flowing
    smooth_sphere(f"{name}_hair", r=0.22*scale, loc=(0, 0.06*scale, -0.05*scale),
                  parent=head_e, mat_=M_HAIR_BLACK_B, scale=(1.05, 1.05, 1.3))
    smooth_sphere(f"{name}_hair_t", r=0.19*scale, loc=(0, 0.02*scale, 0.06*scale),
                  parent=head_e, mat_=M_HAIR_BLACK_B, scale=(1, 1, 0.85))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022*scale,
                      loc=(side*0.06*scale, -0.14*scale, 0.02*scale), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.20, 0.10, 0.05, 1), 0, 0.4,
                                emission=(0.30, 0.18, 0.10), emission_strength=1.5))
    # Lips red
    beveled_cube(f"{name}_lips", (0.10*scale, 0.04*scale, 0.03*scale), loc=(0, -0.17*scale, -0.08*scale),
                 parent=head_e, mat_=M_BIKINI_RED)
    # MASSIVE FEATHER HEADDRESS (signature samba)
    headdress_e = empty(f"{name}_hd_e", (0, 0, 0.20*scale), parent=head_e)
    # Crown band
    cyl(f"{name}_crown", r=0.22*scale, depth=0.08*scale, segs=18,
        loc=(0, 0, 0), parent=headdress_e, mat_=M_FLOAT_GOLD)
    # 30 feathers radiating
    plume_colors = [plume_color, M_PLUME_GOLD, M_PLUME_WHITE, M_PLUME_RED]
    for fi in range(30):
        fa = (fi / 30.0) * math.pi * 2
        f_len = (1.5 + (1.0 if is_queen else 0.0)) * scale
        fea_e = empty(f"{name}_fea_e{fi}", (0.22*scale*math.cos(fa), 0.22*scale*math.sin(fa), 0.05*scale),
                      parent=headdress_e)
        fea_e.rotation_euler = (math.radians(-30), 0, fa + math.pi/2)
        col = plume_colors[fi % len(plume_colors)]
        # Long feather signature
        cyl(f"{name}_fea_quill{fi}", r=0.012*scale, depth=f_len, segs=6,
            loc=(0, 0, f_len/2), parent=fea_e, mat_=col)
        beveled_cube(f"{name}_fea_vane{fi}", (0.08*scale, 0.04*scale, f_len), bevel_offset=0.01,
                     loc=(0, 0, f_len/2), parent=fea_e, mat_=col)
        # Tip puff
        smooth_sphere(f"{name}_fea_tip{fi}", r=0.10*scale, loc=(0, 0, f_len + 0.05*scale),
                      parent=fea_e, mat_=col, scale=(1, 0.4, 1))
    # Back plumes (wings) - signature massive
    back_e = empty(f"{name}_back_e", (0, 0.15*scale, 1.7*scale), parent=base)
    back_e.rotation_euler = (math.radians(-15), 0, 0)
    for bp in range(20):
        ba = (bp - 9.5) * 0.15
        bp_len = (1.8 - abs(ba)*0.3) * scale
        bp_e = empty(f"{name}_bp_e{bp}", (0, 0, 0), parent=back_e)
        bp_e.rotation_euler = (0, 0, ba)
        col = plume_colors[bp % len(plume_colors)]
        cyl(f"{name}_bp{bp}", r=0.015*scale, depth=bp_len, segs=6,
            loc=(0, bp_len/2, 0), parent=bp_e, mat_=col).rotation_euler = (math.radians(90), 0, 0)
        beveled_cube(f"{name}_bp_v{bp}", (0.08*scale, bp_len, 0.04*scale), bevel_offset=0.01,
                     loc=(0, bp_len/2, 0), parent=bp_e, mat_=col)
        # Tip ball
        smooth_sphere(f"{name}_bp_tip{bp}", r=0.10*scale, loc=(0, bp_len + 0.05*scale, 0),
                      parent=bp_e, mat_=col)
    # Arms
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30*scale, 0, 1.92*scale), parent=base)
        sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-50))
        cyl(f"{name}_uarm{side_idx}", r=0.07*scale, depth=0.32*scale, segs=12,
            loc=(0, 0, -0.17*scale), parent=sh, mat_=M_SKIN_BRAZILIAN)
        cyl(f"{name}_fa{side_idx}", r=0.06*scale, depth=0.30*scale, segs=10,
            loc=(0, 0, -0.45*scale), parent=sh, mat_=M_SKIN_BRAZILIAN)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07*scale, loc=(0, 0, -0.60*scale),
                      parent=sh, mat_=M_SKIN_BRAZILIAN)
        # Arm bracelets sequins
        cyl(f"{name}_brac{side_idx}", r=0.07*scale, depth=0.04*scale, segs=12,
            loc=(0, 0, -0.30*scale), parent=sh, mat_=M_SEQUIN)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e, "back": back_e}

dancers = []
# Queen on float center
queen = make_samba_dancer("queen", (-2.5, 8, 2.5), M_BIKINI_RED, M_PLUME_RED, is_queen=True,
                           facing=math.radians(180), scale=1.15)
dancers.append(queen)
# 5 other dancers in parade
dancer_specs = [
    ("d1", (-12, 3, 0), M_BIKINI_GOLD, M_PLUME_GOLD, math.radians(0)),
    ("d2", (-9, 5, 0), M_BIKINI_GREEN, M_PLUME_GREEN, math.radians(10)),
    ("d3", (-6, 3, 0), M_BIKINI_BLUE, M_PLUME_BLUE, math.radians(-10)),
    ("d4", (12, 3, 0), M_BIKINI_PINK, M_PLUME_PINK, math.radians(180)),
    ("d5", (9, 5, 0), M_BIKINI_PURPLE, M_PLUME_PURPLE, math.radians(180)),
]
for spec in dancer_specs:
    name, loc, bik, pl, fac = spec
    d = make_samba_dancer(name, loc, bik, pl, facing=fac)
    dancers.append(d)

# Male dancer
male_e = empty("male_dancer", loc=(0, 5, 0))
male_e.rotation_euler = (0, 0, math.radians(180))
# Pants gold sequins
smooth_cone("ml_pants", r1=0.33, r2=0.25, depth=0.95, segs=14,
            loc=(0, 0, 0.50), parent=male_e, mat_=M_FLOAT_GOLD)
# Sequins on pants
for s in range(30):
    sa = random.uniform(0, math.pi*2)
    sr = random.uniform(0.10, 0.32)
    sz = random.uniform(0.10, 0.80)
    smooth_sphere(f"ml_seq{s}", r=0.025, loc=(sr*math.cos(sa), sr*math.sin(sa), sz),
                  parent=male_e, mat_=M_SEQUIN)
# Bare chest
beveled_cube("ml_torso", (0.40, 0.22, 0.55), bevel_offset=0.05, loc=(0, 0, 1.30),
             parent=male_e, mat_=M_SKIN_DARK)
# Open vest with sequins
for side in (-1, 1):
    beveled_cube(f"ml_vest{side}", (0.10, 0.10, 0.50), bevel_offset=0.03,
                 loc=(side*0.18, -0.13, 1.30), parent=male_e, mat_=M_FLOAT_RED)
# Belt
cyl("ml_belt", r=0.32, depth=0.10, segs=18, loc=(0, 0, 1.00),
    parent=male_e, mat_=M_CAPO_RED_BELT)
# Neck
cyl("ml_neck", r=0.09, depth=0.16, segs=10, loc=(0, 0, 1.66),
    parent=male_e, mat_=M_SKIN_DARK)
# Head
ml_head_e = empty("ml_he", (0, 0, 1.84), parent=male_e)
smooth_sphere("ml_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
              parent=ml_head_e, mat_=M_SKIN_DARK)
smooth_sphere("ml_hair", r=0.20, loc=(0, 0.04, 0.04), parent=ml_head_e, mat_=M_HAIR_BLACK_B,
              scale=(1, 1, 0.85))
# Eyes
for side in (-1, 1):
    smooth_sphere(f"ml_eye{side}", r=0.022, loc=(side*0.06, -0.14, 0.02),
                  parent=ml_head_e,
                  mat_=mat(f"ml_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                            emission=(0.30, 0.15, 0.08), emission_strength=1.5))
# Headdress (smaller)
for fi in range(15):
    fa = (fi - 7) * 0.20
    fea = beveled_cube(f"ml_fea{fi}", (0.05, 0.04, 0.50), bevel_offset=0.01,
                       loc=(math.sin(fa)*0.20, 0.05, 0.40), parent=ml_head_e,
                       mat_=[M_PLUME_RED, M_PLUME_GOLD, M_PLUME_GREEN][fi % 3])
    fea.rotation_euler = (math.radians(-20), 0, fa)
# Arms (snap fingers)
ml_arms = []
for side_idx, side in enumerate((-1, 1)):
    sh = empty(f"ml_sh{side_idx}", (side*0.30, 0, 1.58), parent=male_e)
    sh.rotation_euler = (math.radians(-130), 0, math.radians(side*-50))
    cyl(f"ml_uarm{side_idx}", r=0.08, depth=0.35, segs=12, loc=(0, 0, -0.18), parent=sh, mat_=M_SKIN_DARK)
    cyl(f"ml_fa{side_idx}", r=0.07, depth=0.30, segs=10, loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_DARK)
    smooth_sphere(f"ml_hand{side_idx}", r=0.08, loc=(0, 0, -0.68), parent=sh, mat_=M_SKIN_DARK)
    ml_arms.append(sh)

# ============ 4 PERCUSSIONISTS (batucada signature) ============
def make_percussionist(name, loc, drum_mat, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Pants
    smooth_cone(f"{name}_pants", r1=0.30, r2=0.24, depth=0.90, segs=14,
                loc=(0, 0, 0.45), parent=base, mat_=M_FLOAT_GREEN)
    # Shirt color
    beveled_cube(f"{name}_shirt", (0.42, 0.24, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 1.20), parent=base, mat_=M_FLAG_BR_YELLOW)
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.16, segs=10, loc=(0, 0, 1.55),
        parent=base, mat_=M_SKIN_DARK)
    head_e = empty(f"{name}_he", (0, 0, 1.73), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_DARK)
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.04, 0.05),
                  parent=head_e, mat_=M_HAIR_BLACK_B, scale=(1, 1, 0.85))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.30, 0.15, 0.08), emission_strength=1.0))
    # MASSIVE SURDO DRUM (signature batucada)
    drum_e = empty(f"{name}_drum_e", (0, -0.45, 1.0), parent=base)
    cyl(f"{name}_drum_body", r=0.40, depth=0.60, segs=20,
        loc=(0, 0, 0), parent=drum_e, mat_=drum_mat)
    # Drum skin top + bottom
    cyl(f"{name}_drum_skin_t", r=0.38, depth=0.03, segs=20,
        loc=(0, 0, 0.32), parent=drum_e, mat_=M_DRUM_SKIN)
    cyl(f"{name}_drum_skin_b", r=0.38, depth=0.03, segs=20,
        loc=(0, 0, -0.32), parent=drum_e, mat_=M_DRUM_SKIN)
    # Metal bands signature
    for bd in range(8):
        bda = (bd / 8.0) * math.pi * 2
        beveled_cube(f"{name}_drum_b{bd}", (0.04, 0.04, 0.66), bevel_offset=0.01,
                     loc=(0.40*math.cos(bda), 0.40*math.sin(bda), 0), parent=drum_e, mat_=M_DRUM_GOLD)
    # Strap over shoulder
    beveled_cube(f"{name}_strap", (0.05, 0.04, 1.0), loc=(-0.15, -0.25, 1.30),
                 parent=base, mat_=M_FLAG_BR_GREEN).rotation_euler = (0, math.radians(20), 0)
    # Arms striking drum
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.27, 0, 1.42), parent=base)
        sh.rotation_euler = (math.radians(-110), 0, math.radians(side*-30))
        cyl(f"{name}_uarm{side_idx}", r=0.07, depth=0.30, segs=10,
            loc=(0, 0, -0.15), parent=sh, mat_=M_FLAG_BR_YELLOW)
        cyl(f"{name}_fa{side_idx}", r=0.06, depth=0.28, segs=10,
            loc=(0, 0, -0.42), parent=sh, mat_=M_SKIN_DARK)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.07, loc=(0, 0, -0.58),
                      parent=sh, mat_=M_SKIN_DARK)
        # Drum mallet
        cyl(f"{name}_mallet{side_idx}", r=0.02, depth=0.25, segs=8,
            loc=(0, 0, -0.78), parent=sh, mat_=M_DRUM_BLACK)
        smooth_sphere(f"{name}_mallet_tip{side_idx}", r=0.06, loc=(0, 0, -0.92),
                      parent=sh, mat_=M_DRUM_BLACK)
        arms_e.append(sh)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e}

percussionists = []
perc_specs = [
    ("perc1", (-15, 8, 0), M_DRUM_RED, math.radians(0)),
    ("perc2", (-13, 11, 0), M_FLOAT_BLUE, math.radians(-15)),
    ("perc3", (15, 8, 0), M_DRUM_RED, math.radians(180)),
    ("perc4", (13, 11, 0), M_FLOAT_GREEN, math.radians(165)),
]
for spec in perc_specs:
    name, loc, drum, fac = spec
    p = make_percussionist(name, loc, drum, facing=fac)
    percussionists.append(p)

# ============ 4 CAPOEIRISTAS (signature dance) ============
def make_capoeirista(name, loc, belt_mat, is_flipping=False, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # White pants (signature)
    smooth_cone(f"{name}_pants", r1=0.30, r2=0.22, depth=1.0, segs=14,
                loc=(0, 0, 0.50), parent=base, mat_=M_CAPO_WHITE)
    # Belt (cordão signature)
    cyl(f"{name}_belt", r=0.32, depth=0.10, segs=18,
        loc=(0, 0, 1.05), parent=base, mat_=belt_mat)
    # Torso (bare or shirt)
    beveled_cube(f"{name}_torso", (0.40, 0.22, 0.55), bevel_offset=0.05,
                 loc=(0, 0, 1.40), parent=base, mat_=M_SKIN_DARK)
    # Muscles
    for side in (-1, 1):
        smooth_sphere(f"{name}_pec{side}", r=0.11,
                      loc=(side*0.10, -0.12, 1.55), parent=base,
                      mat_=M_SKIN_DARK, scale=(1, 0.6, 0.7))
    # Neck
    cyl(f"{name}_neck", r=0.09, depth=0.16, segs=10,
        loc=(0, 0, 1.78), parent=base, mat_=M_SKIN_DARK)
    head_e = empty(f"{name}_he", (0, 0, 1.96), parent=base)
    smooth_sphere(f"{name}_head", r=0.18, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_SKIN_DARK)
    smooth_sphere(f"{name}_hair", r=0.20, loc=(0, 0.04, 0.05), parent=head_e,
                  mat_=M_HAIR_BLACK_B, scale=(1, 1, 0.85))
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.022,
                      loc=(side*0.06, -0.14, 0.02), parent=head_e,
                      mat_=mat(f"{name}_ew{side}", (0.10, 0.05, 0.04, 1), 0, 0.4,
                                emission=(0.30, 0.15, 0.08), emission_strength=1.0))
    # Arms (kick pose signature)
    arms_e = []
    for side_idx, side in enumerate((-1, 1)):
        sh = empty(f"{name}_sh{side_idx}", (side*0.30, 0, 1.85), parent=base)
        if is_flipping:
            # Inverted handstand pose
            sh.rotation_euler = (math.radians(180 - 30), 0, math.radians(side*-15))
        else:
            sh.rotation_euler = (math.radians(-100), 0, math.radians(side*-40))
        cyl(f"{name}_uarm{side_idx}", r=0.08, depth=0.35, segs=12,
            loc=(0, 0, -0.18), parent=sh, mat_=M_SKIN_DARK)
        cyl(f"{name}_fa{side_idx}", r=0.07, depth=0.32, segs=10,
            loc=(0, 0, -0.50), parent=sh, mat_=M_SKIN_DARK)
        smooth_sphere(f"{name}_hand{side_idx}", r=0.08, loc=(0, 0, -0.68),
                      parent=sh, mat_=M_SKIN_DARK)
        arms_e.append(sh)
    # If flipping, rotate whole body
    if is_flipping:
        base.rotation_euler = (math.radians(180), 0, facing)
        base.location.z += 1.5  # Lift body
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "arms": arms_e, "is_flipping": is_flipping}

capoeiristas = []
capo_specs = [
    ("cap1", (-7, -5, 0), M_CAPO_RED_BELT, False, math.radians(45)),
    ("cap2", (7, -5, 0), M_CAPO_GREEN_BELT, False, math.radians(-45)),
    ("cap3", (-4, -7, 0), M_CAPO_BLUE_BELT, True, math.radians(20)),
    ("cap4", (4, -7, 0), M_CAPO_RED_BELT, True, math.radians(-20)),
]
for spec in capo_specs:
    name, loc, belt, flip, fac = spec
    c = make_capoeirista(name, loc, belt, is_flipping=flip, facing=fac)
    capoeiristas.append(c)

# ============ 100 SPECTATORS lointains ============
for sp_idx in range(100):
    sa = random.uniform(0, math.pi*2)
    rad = random.uniform(20, 30)
    sx_sp = rad * math.cos(sa)
    sy_sp = rad * math.sin(sa)
    sp_z = 0
    smooth_cone(f"sp_body{sp_idx}", r1=0.30, r2=0.20, depth=0.80, segs=12,
                loc=(sx_sp, sy_sp, sp_z + 0.40),
                mat_=[M_FLOAT_RED, M_FLAG_BR_YELLOW, M_FLAG_BR_GREEN, M_FLOAT_PINK,
                       M_FLOAT_BLUE, M_FLOAT_PURPLE][sp_idx % 6])
    smooth_sphere(f"sp_h{sp_idx}", r=0.13, loc=(sx_sp, sy_sp, sp_z + 0.95),
                  mat_=M_SKIN_BRAZILIAN if sp_idx % 2 == 0 else M_SKIN_DARK)

# ============ LANTERNS overhead (signature carnival) ============
lantern_colors = [M_LANT_FEST, M_LANT_RED, M_LANT_GREEN, M_LANT_BLUE, M_LANT_PINK]
lanterns = []
for li in range(40):
    li_x = (li % 8 - 3.5) * 2.5
    li_y = (li // 8) * 2 - 5
    li_z = random.uniform(7, 12)
    l_e = empty(f"lant{li}", (li_x, li_y, li_z))
    # Chain
    for ci in range(3):
        smooth_sphere(f"lant_ch{li}_{ci}", r=0.03,
                      loc=(0, 0, ci*0.3 + 0.4), parent=l_e, mat_=M_DRUM_BLACK)
    # Body
    smooth_sphere(f"lant_b{li}", r=0.25, loc=(0, 0, 0),
                  parent=l_e, mat_=lantern_colors[li % 5], scale=(1, 1, 1.3))
    l_e["_phase"] = random.uniform(0, math.pi*2)
    lanterns.append(l_e)

# Brazil flag on float
flag_e = empty("br_flag", (0, 5, 5), parent=float_e)
beveled_cube("flag_main", (1.8, 0.10, 1.0), bevel_offset=0.03, loc=(0, 0, 0),
             parent=flag_e, mat_=M_FLAG_BR_GREEN)
# Yellow diamond
diamond = beveled_cube("flag_diam", (1.2, 0.05, 0.65), bevel_offset=0.04, loc=(0, -0.05, 0),
                      parent=flag_e, mat_=M_FLAG_BR_YELLOW)
diamond.rotation_euler = (math.radians(45), 0, 0)
# Blue circle
smooth_sphere("flag_circ", r=0.30, loc=(0, -0.10, 0), parent=flag_e, mat_=M_FLAG_BR_BLUE,
              scale=(1, 0.1, 1))
# Stars (signature)
for st in range(5):
    sta = (st / 5.0) * math.pi * 2
    smooth_sphere(f"flag_star{st}", r=0.025, loc=(0.15*math.cos(sta), -0.12, 0.15*math.sin(sta)),
                  parent=flag_e, mat_=M_FLAG_BR_WHITE)

# ============================================================
# ⭐ 800 CONFETTI + 400 SAMBA SPARKLES (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
conf_colors = [M_CONF_R, M_CONF_G, M_CONF_B, M_CONF_Y, M_CONF_PK, M_CONF_PU, M_CONF_O]
confetti = []
for i in range(800):
    px = random.uniform(-25, 25)
    py = random.uniform(-15, 20)
    pz = random.uniform(2, 18)
    col = conf_colors[i % 7]
    c_obj = beveled_cube(f"conf{i}", (random.uniform(0.08, 0.14),
                                          random.uniform(0.06, 0.10),
                                          random.uniform(0.008, 0.015)), bevel_offset=0.002,
                          loc=(px, py, pz), mat_=col)
    c_obj.rotation_euler = (random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2),
                            random.uniform(0, math.pi*2))
    c_obj["_phase"] = random.uniform(0, math.pi*2)
    c_obj["_base_x"] = px; c_obj["_base_y"] = py; c_obj["_base_z"] = pz
    c_obj["_speed"] = random.uniform(0.5, 1.4)
    c_obj["_drift_x"] = random.uniform(-2.0, 2.0)
    c_obj["_drift_y"] = random.uniform(-2.0, 2.0)
    confetti.append(c_obj)

# 400 samba sparkles
sp_colors = [M_SPARK_G, M_SPARK_A, M_SPARK_W]
samba_sparkles = []
for i in range(400):
    px = random.uniform(-20, 20)
    py = random.uniform(-10, 15)
    pz = random.uniform(1, 12)
    col = sp_colors[i % 3]
    s_obj = smooth_sphere(f"ssp{i}", r=random.uniform(0.06, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=col)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(1.0, 2.5)
    s_obj["_amp_y"] = random.uniform(1.0, 2.5)
    s_obj["_amp_z"] = random.uniform(0.5, 1.5)
    s_obj["_speed"] = random.uniform(0.8, 1.6)
    samba_sparkles.append(s_obj)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Float roll forward
for f in range(1, total_frames + 1, 4):
    t = (f - 1) / fps
    float_e.location.x = math.sin(t * 0.4) * 1.5
    float_e.location.y = 8 + math.sin(t * 0.3) * 0.3
    float_e.rotation_euler = (0, math.sin(t * 1.0) * math.radians(2), 0)
    float_e.keyframe_insert("location", frame=f)
    float_e.keyframe_insert("rotation_euler", frame=f)

# Dragon undulates
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    dragon_e.rotation_euler = (0, 0, math.sin(t * 1.5) * math.radians(8))
    dragon_e.keyframe_insert("rotation_euler", frame=f)

# Samba dancers hip wiggle + plume sway
for d in dancers:
    phase = d["root"]["_phase"]
    base_z = d["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        # Hip wiggle (signature samba)
        d["root"].location.z = base_z + abs(math.sin(t * 4.0 + phase)) * 0.10
        d["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(6),
                                     math.cos(t * 1.8 + phase) * math.radians(4),
                                     d["root"].rotation_euler.z + math.sin(t * 1.5 + phase) * math.radians(15))
        d["root"].keyframe_insert("location", frame=f)
        d["root"].keyframe_insert("rotation_euler", frame=f)
        # Plumes sway
        d["back"].rotation_euler = (math.radians(-15) + math.sin(t * 3.0 + phase) * math.radians(8),
                                      math.cos(t * 2.5 + phase) * math.radians(8), 0)
        d["back"].keyframe_insert("rotation_euler", frame=f)
        # Arms
        for ai, arm in enumerate(d["arms"]):
            base_rx = arm.rotation_euler.x
            wave = math.sin(t * 2.5 + phase + ai * math.pi) * math.radians(20)
            arm.rotation_euler = (base_rx + wave, 0, arm.rotation_euler.z)
            arm.keyframe_insert("rotation_euler", frame=f)
        # Head
        d["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(6), 0,
                                    math.sin(t * 1.8 + phase) * math.radians(20))
        d["he"].keyframe_insert("rotation_euler", frame=f)

# Male dancer dance
for f in range(1, total_frames + 1, 3):
    t = (f - 1) / fps
    male_e.location.z = abs(math.sin(t * 4.0)) * 0.10
    male_e.rotation_euler = (math.sin(t * 1.5) * math.radians(5),
                              math.cos(t * 1.2) * math.radians(4),
                              math.radians(180) + math.sin(t * 1.0) * math.radians(15))
    male_e.keyframe_insert("location", frame=f)
    male_e.keyframe_insert("rotation_euler", frame=f)
    for ai, arm in enumerate(ml_arms):
        wave = math.sin(t * 3.0 + ai * math.pi) * math.radians(20)
        arm.rotation_euler = (math.radians(-130) + wave, 0, math.radians((-1 if ai==0 else 1)*-50))
        arm.keyframe_insert("rotation_euler", frame=f)

# Percussionists strike drums
for p in percussionists:
    phase = p["root"]["_phase"]
    base_z = p["root"].location.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        p["root"].location.z = base_z + math.sin(t * 2.0 + phase) * 0.04
        p["root"].keyframe_insert("location", frame=f)
        # Arms strike (fast batucada signature)
        for ai, arm in enumerate(p["arms"]):
            strike = math.sin(t * 8.0 + phase + ai * math.pi) * math.radians(35)
            arm.rotation_euler = (math.radians(-110) + strike, 0, math.radians(side*-30))
            arm.keyframe_insert("rotation_euler", frame=f)
        p["he"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(8), 0,
                                    math.sin(t * 1.5 + phase) * math.radians(15))
        p["he"].keyframe_insert("rotation_euler", frame=f)

# Capoeiristas flip/kick
for c in capoeiristas:
    phase = c["root"]["_phase"]
    base_z = c["root"].location.z
    base_rz = c["root"].rotation_euler.z
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        if c["is_flipping"]:
            # Continuous rotation flip
            c["root"].location.z = 1.5 + math.sin(t * 3.0 + phase) * 0.5
            c["root"].rotation_euler = (math.radians(180) + math.sin(t * 2.0 + phase) * math.radians(15),
                                          math.cos(t * 2.5 + phase) * math.radians(10),
                                          base_rz + t * 1.5)
        else:
            c["root"].location.z = base_z + abs(math.sin(t * 2.5 + phase)) * 0.15
            c["root"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(15),
                                          math.cos(t * 1.8 + phase) * math.radians(12),
                                          base_rz)
        c["root"].keyframe_insert("location", frame=f)
        c["root"].keyframe_insert("rotation_euler", frame=f)

# Christ Redeemer halo pulse
for hi in range(3):
    halo_name = f"christ_halo{hi}"
    if halo_name in bpy.data.objects:
        halo = bpy.data.objects[halo_name]
        for f in range(1, total_frames + 1, 4):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 1.0 + hi*0.3) * 0.10
            halo.scale = (s, s, s)
            halo.keyframe_insert("scale", frame=f)

# Lanterns pulse
for l in lanterns:
    phase = l["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        s = 1 + math.sin(t * 2.5 + phase) * 0.15
        l.scale = (s, s, s)
        l.keyframe_insert("scale", frame=f)

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

# Sun halos
for obj in bpy.data.objects:
    if obj.name.startswith("sun_halo"):
        for f in range(1, total_frames + 1, 6):
            t = (f - 1) / fps
            s = 1 + math.sin(t * 0.7) * 0.05
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=f)

# ============================================================
# ⭐⭐⭐ 800 CONFETTI + 400 SAMBA SPARKLES (signature Rio carnival)
# ============================================================
for c in confetti:
    phase = c["_phase"]; speed = c["_speed"]
    bx, by, bz = c["_base_x"], c["_base_y"], c["_base_z"]
    drift_x = c["_drift_x"]; drift_y = c["_drift_y"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Fall + drift swirl
        z = bz - (speed * t * 0.4) % 16
        x = bx + drift_x * math.sin(t * 1.4 + phase) * 0.8
        y = by + drift_y * math.cos(t * 1.2 + phase) * 0.8
        c.location = (x, y, max(0.3, z))
        c.rotation_euler = (phase + t * 2.2, phase + t * 1.8, phase + t * 2.5)
        c.keyframe_insert("location", frame=f)
        c.keyframe_insert("rotation_euler", frame=f)

# 400 SAMBA SPARKLES vortex
for s in samba_sparkles:
    phase = s["_phase"]; speed = s["_speed"]
    bx, by, bz = s["_base_x"], s["_base_y"], s["_base_z"]
    ax, ay, az = s["_amp_x"], s["_amp_y"], s["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        s.location = (x, y, max(0.3, z))
        sc = 1 + math.sin(t * 5.0 + phase) * 0.5
        s.scale = (sc, sc, sc)
        s.keyframe_insert("location", frame=f)
        s.keyframe_insert("scale", frame=f)

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
out_glb = os.path.join(out_dir, "pbr_brazil_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_brazilian_carnival_rio] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_brazilian_carnival_rio] ONE pavement + Copacabana wave + Sugarloaf + Corcovado + Christ Redeemer arms spread + carnival float + dragon + 6 samba dancers + male + 4 percussionists + 4 capoeiristas + 100 spectators + 40 lanterns + 800 CONFETTI + 400 SAMBA SPARKLES")
print("⭐ FIXES: 1 ground + 800 confetti + 400 samba sparkles (signature Rio carnival mandatory) ⭐")
