"""
proc_african_savanna_safari_acacia.py — 241e procédural AuroraIA (106e qualité)
African savanna safari sunset: 5 acacias + giraffes + lions + elephants + zebras + impalas + rhinos + hippos + flamingos + crocodile + 600 dust + 400 birds
FIXES : 1 ground + 600 dust + 400 exotic birds (signature thematic particles)
"""
import bpy, bmesh, math, random, os

random.seed(0x70AB241)

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

# Sunset palette
M_SKY_TOP = mat("sky_t", (0.95, 0.50, 0.20, 1.0), 0.0, 0.7, emission=(0.95,0.50,0.20), emission_strength=2.0)
M_SKY_BOT = mat("sky_b", (1.0, 0.78, 0.30, 1.0), 0.0, 0.7, emission=(1.0,0.78,0.30), emission_strength=2.5)
M_SUN = mat("sun", (1.0, 0.85, 0.40, 1.0), 0.0, 0.1, emission=(1.0,0.78,0.30), emission_strength=18.0)

# Ground
M_GRASS_OCHRE = mat("grass_o", (0.75, 0.60, 0.30, 1.0), 0.0, 0.85, emission=(0.70,0.55,0.28), emission_strength=0.5)
M_GRASS_GOLD = mat("grass_g", (0.85, 0.65, 0.30, 1.0), 0.0, 0.80, emission=(0.78,0.60,0.28), emission_strength=0.6)
M_DIRT_RED = mat("dirt", (0.55, 0.30, 0.18, 1.0), 0.0, 0.85)
M_GRASS_TUFT = mat("g_tuft", (0.55, 0.45, 0.18, 1.0), 0.0, 0.80)

# Acacia tree
M_TRUNK_DARK = mat("trunk_d", (0.28, 0.18, 0.10, 1.0), 0.0, 0.85, emission=(0.25,0.16,0.10), emission_strength=0.3)
M_LEAVES_ACACIA = mat("leaves_a", (0.30, 0.45, 0.18, 1.0), 0.0, 0.75, emission=(0.28,0.42,0.18), emission_strength=0.6)
M_LEAVES_DRY = mat("leaves_d", (0.55, 0.55, 0.18, 1.0), 0.0, 0.80, emission=(0.50,0.50,0.18), emission_strength=0.7)

# Animal colors
# Giraffe
M_GIRAFFE_TAN = mat("gir_t", (0.92, 0.78, 0.45, 1.0), 0.0, 0.75, emission=(0.85,0.72,0.42), emission_strength=0.5)
M_GIRAFFE_SPOT = mat("gir_s", (0.55, 0.32, 0.10, 1.0), 0.0, 0.75)
M_GIRAFFE_MANE = mat("gir_m", (0.40, 0.22, 0.08, 1.0), 0.0, 0.85)

# Lion
M_LION_GOLD = mat("lion_g", (0.85, 0.62, 0.28, 1.0), 0.0, 0.70, emission=(0.80,0.58,0.28), emission_strength=0.5)
M_LION_MANE = mat("lion_m", (0.55, 0.30, 0.10, 1.0), 0.0, 0.85, emission=(0.50,0.28,0.10), emission_strength=0.4)
M_LION_BELLY = mat("lion_b", (0.95, 0.85, 0.55, 1.0), 0.0, 0.70)
M_LION_EYE = mat("lion_e", (0.95, 0.78, 0.20, 1.0), 0.0, 0.10, emission=(0.95,0.78,0.20), emission_strength=8.0)
M_NOSE_PINK = mat("nose", (0.55, 0.30, 0.30, 1.0), 0.0, 0.30)

# Elephant
M_ELEPHANT_GREY = mat("el_g", (0.55, 0.50, 0.48, 1.0), 0.0, 0.80, emission=(0.50,0.45,0.45), emission_strength=0.4)
M_ELEPHANT_DARK = mat("el_d", (0.40, 0.38, 0.36, 1.0), 0.0, 0.85)
M_ELEPHANT_TUSK = mat("el_t", (0.95, 0.92, 0.85, 1.0), 0.0, 0.30, emission=(0.92,0.90,0.85), emission_strength=0.8)

# Zebra
M_ZEBRA_WHITE = mat("zb_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.70, emission=(0.90,0.88,0.82), emission_strength=0.6)
M_ZEBRA_BLACK = mat("zb_b", (0.08, 0.06, 0.06, 1.0), 0.0, 0.80)
M_ZEBRA_MANE = mat("zb_m", (0.30, 0.25, 0.20, 1.0), 0.0, 0.85)

# Gnu / Wildebeest
M_GNU_DARK = mat("gnu_d", (0.30, 0.22, 0.18, 1.0), 0.0, 0.80, emission=(0.28,0.20,0.18), emission_strength=0.3)
M_GNU_LIGHT = mat("gnu_l", (0.50, 0.38, 0.28, 1.0), 0.0, 0.75)

# Impala
M_IMPALA_TAN = mat("imp_t", (0.85, 0.55, 0.28, 1.0), 0.0, 0.70, emission=(0.80,0.50,0.28), emission_strength=0.5)
M_IMPALA_WHITE = mat("imp_w", (0.95, 0.92, 0.85, 1.0), 0.0, 0.65)

# Rhino
M_RHINO_GREY = mat("rh_g", (0.48, 0.45, 0.40, 1.0), 0.0, 0.80, emission=(0.45,0.42,0.38), emission_strength=0.3)
M_RHINO_HORN = mat("rh_h", (0.62, 0.55, 0.45, 1.0), 0.0, 0.55)

# Hippo
M_HIPPO_GREY = mat("hp_g", (0.42, 0.35, 0.32, 1.0), 0.0, 0.80, emission=(0.40,0.32,0.30), emission_strength=0.4)
M_HIPPO_PINK = mat("hp_p", (0.85, 0.55, 0.50, 1.0), 0.0, 0.70)

# Crocodile
M_CROC_GREEN = mat("cr_g", (0.30, 0.35, 0.18, 1.0), 0.0, 0.80, emission=(0.28,0.32,0.18), emission_strength=0.4)
M_CROC_DARK = mat("cr_d", (0.18, 0.22, 0.10, 1.0), 0.0, 0.85)
M_CROC_EYE = mat("cr_e", (0.85, 0.78, 0.18, 1.0), 0.0, 0.10, emission=(0.85,0.78,0.18), emission_strength=6.0)

# Flamingo
M_FLAMINGO_PINK = mat("fl_p", (0.95, 0.55, 0.65, 1.0), 0.0, 0.55, emission=(0.92,0.52,0.62), emission_strength=1.2)
M_FLAMINGO_BEAK = mat("fl_bk", (0.20, 0.15, 0.10, 1.0), 0.0, 0.45)
M_FLAMINGO_LEG = mat("fl_l", (0.85, 0.55, 0.45, 1.0), 0.0, 0.45)

# River
M_WATER_RIVER = mat("water", (0.35, 0.55, 0.65, 1.0), 0.1, 0.20, emission=(0.30,0.50,0.62), emission_strength=1.5, alpha=0.78)
M_WATER_DEEP = mat("water_d", (0.20, 0.38, 0.50, 1.0), 0.1, 0.30, alpha=0.85)

# Termite mound
M_TERMITE = mat("term", (0.65, 0.40, 0.22, 1.0), 0.0, 0.85, emission=(0.60,0.38,0.22), emission_strength=0.3)

# Bird colors
M_BIRD_R = mat("bird_r", (0.95, 0.25, 0.20, 1.0), 0.0, 0.40, emission=(0.92,0.25,0.20), emission_strength=2.0)
M_BIRD_Y = mat("bird_y", (1.0, 0.85, 0.25, 1.0), 0.0, 0.40, emission=(1.0,0.85,0.25), emission_strength=2.2)
M_BIRD_B = mat("bird_b", (0.20, 0.55, 0.85, 1.0), 0.0, 0.40, emission=(0.20,0.55,0.85), emission_strength=2.0)
M_BIRD_G = mat("bird_g", (0.30, 0.85, 0.40, 1.0), 0.0, 0.40, emission=(0.30,0.85,0.40), emission_strength=2.0)
M_BIRD_BK = mat("bird_bk", (0.10, 0.08, 0.08, 1.0), 0.0, 0.55)

# Dust
M_DUST = mat("dust", (0.95, 0.78, 0.45, 1.0), 0.0, 0.50, emission=(0.92,0.75,0.42), emission_strength=2.0, alpha=0.45)

# Tooth
M_TOOTH = mat("tooth", (0.95, 0.92, 0.85, 1.0), 0.0, 0.40)

BIRD_COLORS = [M_BIRD_R, M_BIRD_Y, M_BIRD_B, M_BIRD_G]

# ============ SKY ============
sky = smooth_sphere("sky", r=220, segs=32, rings=20, loc=(0,0,0), mat_=M_SKY_TOP)
sky.scale = (1,1,0.55)
# Lower sky horizon glow
sky_horizon = smooth_sphere("sky_h", r=180, segs=32, rings=16, loc=(0,0,5), mat_=M_SKY_BOT)
sky_horizon.scale = (1,1,0.25)

# SUN (signature huge orange setting)
sun_e = empty("sun_e", (0, 60, 12))
sun_main = smooth_sphere("sun", r=8, segs=28, rings=20, loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)
# Sun halo
for sh in range(4):
    smooth_sphere(f"sun_halo{sh}", r=8 + sh*0.8, segs=24, rings=16,
                  loc=(0, 0, 0), parent=sun_e, mat_=M_SUN)

# ============ ONE clean ocher grass ground ============
ground = beveled_cube("ground", (140, 140, 0.5), bevel_offset=0.10, loc=(0, 0, -0.25), mat_=M_GRASS_OCHRE)
# Organic earth variation
for i in range(150):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(2, 60)
    smooth_sphere(f"earth{i}", r=random.uniform(0.4, 0.9), segs=10, rings=8,
                  loc=(rad*math.cos(a), rad*math.sin(a), 0.10),
                  mat_=M_GRASS_GOLD if i % 2 == 0 else M_DIRT_RED,
                  scale=(1.6, 1.5, 0.20))

# Grass tufts (signature savanna)
for gt in range(120):
    a = random.uniform(0, math.pi*2)
    rad = random.uniform(3, 55)
    gtx = rad*math.cos(a)
    gty = rad*math.sin(a)
    for sti in range(random.randint(3, 6)):
        sa = (sti / 6.0) * math.pi * 2
        cyl(f"gt{gt}_{sti}", r=0.02, depth=random.uniform(0.40, 0.70), segs=6,
            loc=(gtx + math.cos(sa)*0.08, gty + math.sin(sa)*0.08, 0.25),
            mat_=M_GRASS_TUFT)

# ============ RIVER (serpentine signature) ============
river_pts = []
for ri in range(40):
    river_y = -45 + ri * 2.5
    river_x = math.sin(ri * 0.3) * 8 + 20
    river_pts.append((river_x, river_y, 0.05))

for ri in range(len(river_pts) - 1):
    rx1, ry1, rz1 = river_pts[ri]
    rx2, ry2, rz2 = river_pts[ri+1]
    rmidx = (rx1 + rx2) / 2; rmidy = (ry1 + ry2) / 2
    rlen = math.sqrt((rx2-rx1)**2 + (ry2-ry1)**2) + 0.5
    rang = math.atan2(ry2-ry1, rx2-rx1)
    seg = beveled_cube(f"river{ri}", (rlen, 4, 0.15), bevel_offset=0.04,
                       loc=(rmidx, rmidy, 0.18), mat_=M_WATER_RIVER)
    seg.rotation_euler = (0, 0, rang)
    # Deeper water in middle
    seg2 = beveled_cube(f"river_d{ri}", (rlen*0.95, 3, 0.10), bevel_offset=0.03,
                        loc=(rmidx, rmidy, 0.22), mat_=M_WATER_DEEP)
    seg2.rotation_euler = (0, 0, rang)

# ============ 5 ACACIA TREES (signature umbrella canopy) ============
def make_acacia(name, loc, scale=1.0):
    base = empty(name, loc)
    # Trunk
    cyl(f"{name}_trunk", r=0.40*scale, depth=4*scale, segs=14, loc=(0, 0, 2*scale),
        parent=base, mat_=M_TRUNK_DARK)
    # Branches splitting up
    for bi in range(5):
        ba = (bi / 5.0) * math.pi * 2 + random.uniform(-0.3, 0.3)
        br_e = empty(f"{name}_br{bi}_e", (0, 0, 3.5*scale), parent=base)
        br_e.rotation_euler = (math.radians(random.uniform(35, 55)), 0, ba)
        cyl(f"{name}_br{bi}", r=0.15*scale, depth=2.5*scale, segs=10, loc=(0, 0, 1.25*scale),
            parent=br_e, mat_=M_TRUNK_DARK)
    # CANOPY (flat umbrella signature)
    canopy_z = 6*scale
    # Main flat dome
    smooth_sphere(f"{name}_canopy", r=4*scale, segs=22, rings=14, loc=(0, 0, canopy_z),
                  parent=base, mat_=M_LEAVES_ACACIA, scale=(1.3, 1.3, 0.30))
    # Leaf clusters around
    for li in range(35):
        la = random.uniform(0, math.pi*2)
        lr = random.uniform(0.8, 4.0) * scale
        lz = canopy_z + random.uniform(-0.3, 0.4)
        smooth_sphere(f"{name}_cl{li}", r=random.uniform(0.4, 0.7)*scale, segs=14, rings=10,
                      loc=(lr*math.cos(la), lr*math.sin(la), lz),
                      parent=base, mat_=M_LEAVES_DRY if li % 4 == 0 else M_LEAVES_ACACIA)
    base["_phase"] = random.uniform(0, math.pi*2)
    return base

acacias = []
acacia_pos = [(-30, -10, 0), (-25, 15, 0), (25, -25, 0), (35, 20, 0), (-5, -35, 0)]
for i, (ax, ay, az) in enumerate(acacia_pos):
    a = make_acacia(f"acacia{i}", (ax, ay, az), scale=random.uniform(1.0, 1.4))
    acacias.append(a)

# ============ 4 GIRAFFES (signature) ============
def make_giraffe(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    body_e = empty(f"{name}_body_e", (0, 0, 3.5*scale), parent=base)
    smooth_sphere(f"{name}_body", r=0.7*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=body_e, mat_=M_GIRAFFE_TAN, scale=(1.8, 1.0, 1.1))
    # Spots
    for sp in range(35):
        spa = random.uniform(0, math.pi*2); spe = random.uniform(0, math.pi)
        sp_x = math.sin(spe)*math.cos(spa) * 1.1*scale
        sp_y = math.sin(spe)*math.sin(spa) * 0.6*scale
        sp_z = math.cos(spe) * 0.7*scale
        smooth_sphere(f"{name}_spot{sp}", r=random.uniform(0.10, 0.18)*scale,
                      loc=(sp_x, sp_y, sp_z), parent=body_e, mat_=M_GIRAFFE_SPOT,
                      scale=(1, 1, 0.3))
    # 4 long legs
    legs_e = []
    for x in (-1, 1):
        for y in (-1, 1):
            l_e = empty(f"{name}_l{x}{y}_e", (x*0.55*scale, y*0.35*scale, 3.4*scale), parent=base)
            cyl(f"{name}_l{x}{y}", r=0.10*scale, depth=3.4*scale, segs=10, loc=(0, 0, -1.7*scale),
                parent=l_e, mat_=M_GIRAFFE_TAN)
            # Hoof
            cyl(f"{name}_h{x}{y}", r=0.12*scale, depth=0.15*scale, segs=10, loc=(0, 0, -3.4*scale),
                parent=l_e, mat_=M_TRUNK_DARK)
            legs_e.append(l_e)
    # LONG NECK (signature)
    neck_e = empty(f"{name}_neck_e", (1.2*scale, 0, 4*scale), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    # Neck segments
    for ni in range(5):
        cyl(f"{name}_neck{ni}", r=0.20*scale - ni*0.01, depth=0.50*scale, segs=12,
            loc=(0, 0, ni*0.50*scale), parent=neck_e, mat_=M_GIRAFFE_TAN)
        # Spots on neck
        for sp in range(3):
            spa = (sp / 3.0) * math.pi * 2
            smooth_sphere(f"{name}_nspot{ni}_{sp}", r=0.06*scale,
                          loc=(math.cos(spa)*0.21*scale, math.sin(spa)*0.21*scale, ni*0.50*scale),
                          parent=neck_e, mat_=M_GIRAFFE_SPOT, scale=(1, 1, 0.4))
    # Mane on back of neck
    for mn in range(5):
        beveled_cube(f"{name}_mane{mn}", (0.05*scale, 0.20*scale, 0.20*scale), bevel_offset=0.01,
                     loc=(-0.20*scale, 0, mn*0.50*scale + 0.20*scale),
                     parent=neck_e, mat_=M_GIRAFFE_MANE)
    # HEAD
    head_e = empty(f"{name}_he", (0, 0, 2.5*scale), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.30*scale, segs=18, rings=14, loc=(0.20*scale, 0, 0),
                  parent=head_e, mat_=M_GIRAFFE_TAN, scale=(1.5, 0.9, 0.9))
    # 2 horns ossicones (signature)
    for side in (-1, 1):
        cyl(f"{name}_oss{side}", r=0.04*scale, depth=0.25*scale, segs=8,
            loc=(0.05*scale, side*0.10*scale, 0.20*scale), parent=head_e, mat_=M_GIRAFFE_MANE)
        smooth_sphere(f"{name}_oss_tip{side}", r=0.05*scale,
                      loc=(0.05*scale, side*0.10*scale, 0.35*scale), parent=head_e, mat_=M_GIRAFFE_MANE)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10*scale,
                      loc=(0.05*scale, side*0.20*scale, 0.10*scale), parent=head_e,
                      mat_=M_GIRAFFE_TAN, scale=(0.5, 1, 1))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.05*scale,
                      loc=(0.30*scale, side*0.15*scale, 0.08*scale), parent=head_e, mat_=M_LION_EYE)
        smooth_sphere(f"{name}_pup{side}", r=0.025*scale,
                      loc=(0.34*scale, side*0.15*scale, 0.08*scale), parent=head_e, mat_=M_ZEBRA_BLACK)
    # Snout
    smooth_sphere(f"{name}_snout", r=0.18*scale, loc=(0.45*scale, 0, -0.05*scale),
                  parent=head_e, mat_=M_GIRAFFE_TAN, scale=(1.2, 0.8, 0.8))
    # Tail
    tail_e = empty(f"{name}_tail_e", (-1.3*scale, 0, 3.5*scale), parent=base)
    cyl(f"{name}_tail", r=0.04*scale, depth=1.5*scale, segs=8, loc=(0, 0, -0.75*scale),
        parent=tail_e, mat_=M_GIRAFFE_TAN)
    smooth_sphere(f"{name}_tail_t", r=0.10*scale, loc=(0, 0, -1.6*scale),
                  parent=tail_e, mat_=M_GIRAFFE_MANE, scale=(0.6, 0.6, 1.4))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_e, "tail": tail_e, "legs": legs_e}

giraffes = []
giraffe_pos = [(-10, -8, math.radians(45)), (-15, 8, math.radians(-30)),
                (5, 12, math.radians(180)), (15, -15, math.radians(110))]
for i, (gx, gy, fac) in enumerate(giraffe_pos):
    g = make_giraffe(f"giraffe{i}", (gx, gy, 0), scale=1.2, facing=fac)
    giraffes.append(g)

# ============ 6 LIONS (family signature with mane male + cubs) ============
def make_lion(name, loc, scale=1.0, facing=0, is_male=False, is_cub=False):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    if is_cub:
        scale *= 0.45
    # Body
    body_e = empty(f"{name}_body_e", (0, 0, 0.85*scale), parent=base)
    smooth_sphere(f"{name}_body", r=0.6*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=body_e, mat_=M_LION_GOLD, scale=(1.7, 0.9, 1.0))
    # Belly white
    smooth_sphere(f"{name}_belly", r=0.5*scale, segs=18, rings=12, loc=(0, 0, -0.25*scale),
                  parent=body_e, mat_=M_LION_BELLY, scale=(1.4, 0.8, 0.4))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            l_e = empty(f"{name}_l{x}{y}_e", (x*0.5*scale, y*0.30*scale, 0.85*scale), parent=base)
            cyl(f"{name}_l{x}{y}", r=0.10*scale, depth=0.85*scale, segs=10, loc=(0, 0, -0.42*scale),
                parent=l_e, mat_=M_LION_GOLD)
            # Paw
            smooth_sphere(f"{name}_p{x}{y}", r=0.13*scale, loc=(0, 0, -0.85*scale),
                          parent=l_e, mat_=M_LION_GOLD, scale=(1, 1.1, 0.6))
    # Tail
    tail_e = empty(f"{name}_tail_e", (-1.0*scale, 0, 0.9*scale), parent=base)
    cyl(f"{name}_tail", r=0.04*scale, depth=1.2*scale, segs=8, loc=(0, 0, 0.20*scale),
        parent=tail_e, mat_=M_LION_GOLD).rotation_euler = (math.radians(45), 0, 0)
    # Tail tuft
    smooth_sphere(f"{name}_tail_tuft", r=0.10*scale, loc=(0.7*scale, 0, 0.7*scale),
                  parent=tail_e, mat_=M_LION_MANE)
    # HEAD
    head_e = empty(f"{name}_he", (1.0*scale, 0, 0.85*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.40*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_LION_GOLD, scale=(1.1, 1.0, 1.0))
    # MANE (signature male)
    if is_male:
        for mi in range(20):
            ma_e = (mi / 20.0) * math.pi * 2
            mp = (mi / 20.0) * math.pi
            mx_m = math.cos(ma_e)*0.45*scale
            my_m = math.sin(ma_e)*0.45*scale*0.7
            mz_m = math.cos(mp)*0.15*scale
            smooth_sphere(f"{name}_mane{mi}", r=0.18*scale,
                          loc=(mx_m, my_m, mz_m),
                          parent=head_e, mat_=M_LION_MANE)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.08*scale,
                      loc=(-0.05*scale, side*0.22*scale, 0.32*scale), parent=head_e,
                      mat_=M_LION_GOLD, scale=(0.8, 1, 1))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06*scale,
                      loc=(0.30*scale, side*0.15*scale, 0.05*scale), parent=head_e, mat_=M_LION_EYE)
        smooth_sphere(f"{name}_pup{side}", r=0.025*scale,
                      loc=(0.34*scale, side*0.15*scale, 0.05*scale), parent=head_e, mat_=M_ZEBRA_BLACK)
    # Snout
    smooth_sphere(f"{name}_snout", r=0.20*scale, loc=(0.35*scale, 0, -0.08*scale),
                  parent=head_e, mat_=M_LION_BELLY, scale=(1, 0.9, 0.8))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.05*scale, loc=(0.50*scale, 0, 0),
                  parent=head_e, mat_=M_NOSE_PINK)
    # Jaw with teeth (signature open if male roar)
    jaw_e = empty(f"{name}_jaw_e", (0.30*scale, 0, -0.15*scale), parent=head_e)
    smooth_sphere(f"{name}_jaw", r=0.15*scale, loc=(0.10*scale, 0, -0.05*scale),
                  parent=jaw_e, mat_=M_LION_BELLY, scale=(1.2, 0.8, 0.6))
    # Teeth
    for ti2 in range(4):
        cyl(f"{name}_th{ti2}", r=0.018*scale, depth=0.06*scale, segs=6,
            loc=(0.22*scale + (ti2-1.5)*0.04*scale, 0, -0.03*scale),
            parent=jaw_e, mat_=M_TOOTH)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "tail": tail_e, "jaw": jaw_e}

lions = []
lion_pos = [(-3, 18, math.radians(180), True, False),  # male
            (-5, 17, math.radians(170), False, False),  # female
            (-1, 17, math.radians(180), False, False),  # female
            (-4, 16, math.radians(180), False, True),   # cub
            (-2, 16, math.radians(190), False, True),   # cub
            (-6, 15, math.radians(150), False, True)]   # cub
for i, (lx, ly, fac, male, cub) in enumerate(lion_pos):
    l = make_lion(f"lion{i}", (lx, ly, 0), scale=1.0, facing=fac, is_male=male, is_cub=cub)
    lions.append(l)

# ============ 8 ELEPHANTS (signature trumpets) ============
def make_elephant(name, loc, scale=1.0, facing=0, is_baby=False):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    if is_baby:
        scale *= 0.5
    # Body
    smooth_sphere(f"{name}_body", r=1.2*scale, segs=22, rings=16, loc=(0, 0, 1.8*scale),
                  parent=base, mat_=M_ELEPHANT_GREY, scale=(1.5, 1.0, 1.0))
    # 4 thick legs (signature pillars)
    for x in (-1, 1):
        for y in (-1, 1):
            l_e = empty(f"{name}_l{x}{y}_e", (x*0.85*scale, y*0.55*scale, 1.8*scale), parent=base)
            cyl(f"{name}_l{x}{y}", r=0.35*scale, depth=1.6*scale, segs=14, loc=(0, 0, -0.8*scale),
                parent=l_e, mat_=M_ELEPHANT_GREY)
            # Foot pad
            cyl(f"{name}_pad{x}{y}", r=0.40*scale, depth=0.20*scale, segs=14, loc=(0, 0, -1.7*scale),
                parent=l_e, mat_=M_ELEPHANT_DARK)
            # Toenails (4 per foot)
            for tn in range(4):
                tna = (tn / 4.0) * math.pi - math.pi/2
                smooth_sphere(f"{name}_tn{x}{y}_{tn}", r=0.06*scale,
                              loc=(math.cos(tna)*0.32*scale, math.sin(tna)*0.32*scale, -1.75*scale),
                              parent=l_e, mat_=M_TOOTH, scale=(1, 1, 0.5))
    # HEAD
    head_e = empty(f"{name}_he", (1.5*scale, 0, 2.5*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.7*scale, segs=22, rings=16, loc=(0, 0, 0),
                  parent=head_e, mat_=M_ELEPHANT_GREY, scale=(1.0, 0.9, 1.1))
    # HUGE EARS (signature)
    for side in (-1, 1):
        ear = beveled_cube(f"{name}_ear{side}", (0.10*scale, 1.0*scale, 1.1*scale), bevel_offset=0.10,
                          loc=(-0.30*scale, side*0.80*scale, 0.05*scale), parent=head_e, mat_=M_ELEPHANT_GREY)
        ear.rotation_euler = (0, 0, math.radians(side*30))
    # TRUNK (signature long curved)
    trunk_e = empty(f"{name}_tr_e", (0.55*scale, 0, -0.25*scale), parent=head_e)
    trunk_e.rotation_euler = (math.radians(20), 0, 0)
    for ti3 in range(7):
        ti3_z = -ti3 * 0.30 * scale
        # Curl pattern
        curl_offset_x = ti3 * 0.15 * scale
        cyl(f"{name}_tr{ti3}", r=(0.28 - ti3*0.025)*scale, depth=0.32*scale, segs=14,
            loc=(curl_offset_x, 0, ti3_z), parent=trunk_e, mat_=M_ELEPHANT_GREY)
    # TUSKS (signature)
    for side in (-1, 1):
        tusk_e = empty(f"{name}_tk{side}_e", (0.5*scale, side*0.20*scale, -0.30*scale), parent=head_e)
        tusk_e.rotation_euler = (math.radians(35), 0, math.radians(side*-10))
        smooth_cone(f"{name}_tk{side}", r1=0.08*scale, r2=0.02*scale, depth=0.80*scale, segs=14,
                    loc=(0, 0, -0.40*scale), parent=tusk_e, mat_=M_ELEPHANT_TUSK)
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06*scale,
                      loc=(0.30*scale, side*0.45*scale, 0.20*scale), parent=head_e, mat_=M_LION_EYE)
        smooth_sphere(f"{name}_pup{side}", r=0.025*scale,
                      loc=(0.34*scale, side*0.45*scale, 0.20*scale), parent=head_e, mat_=M_ZEBRA_BLACK)
    # Tail
    tail_e = empty(f"{name}_tail_e", (-1.7*scale, 0, 2.0*scale), parent=base)
    cyl(f"{name}_tail", r=0.06*scale, depth=0.8*scale, segs=8, loc=(0, 0, -0.40*scale),
        parent=tail_e, mat_=M_ELEPHANT_GREY)
    # Tail tuft
    smooth_sphere(f"{name}_tail_tuft", r=0.10*scale, loc=(0, 0, -0.85*scale),
                  parent=tail_e, mat_=M_ELEPHANT_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "trunk": trunk_e, "tail": tail_e, "he": head_e}

elephants = []
elephant_pos = [(-20, 25, math.radians(-30), False), (-25, 22, math.radians(-30), False),
                (-18, 28, math.radians(0), False), (-22, 28, math.radians(-30), False),
                (-21, 24, math.radians(-30), True),  # baby
                (-19, 22, math.radians(-30), True),  # baby
                (-23, 25, math.radians(0), True),    # baby
                (-26, 24, math.radians(-30), False)]
for i, (ex, ey, fac, baby) in enumerate(elephant_pos):
    e = make_elephant(f"elephant{i}", (ex, ey, 0), scale=1.4, facing=fac, is_baby=baby)
    elephants.append(e)

# ============ 6 ZEBRAS (signature striped) ============
def make_zebra(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    body_e = empty(f"{name}_body_e", (0, 0, 1.1*scale), parent=base)
    smooth_sphere(f"{name}_body", r=0.55*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=body_e, mat_=M_ZEBRA_WHITE, scale=(1.8, 0.9, 1.0))
    # STRIPES (signature wrap around)
    for st in range(14):
        stripe_x = -0.95*scale + st * 0.15*scale
        stripe = cyl(f"{name}_st{st}", r=0.56*scale, depth=0.08*scale, segs=18,
                     loc=(stripe_x, 0, 0), parent=body_e, mat_=M_ZEBRA_BLACK)
        stripe.rotation_euler = (0, math.radians(90), 0)
        stripe.scale = (1, 0.9, 1)
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            l_e = empty(f"{name}_l{x}{y}_e", (x*0.55*scale, y*0.30*scale, 1.1*scale), parent=base)
            cyl(f"{name}_l{x}{y}", r=0.07*scale, depth=1.1*scale, segs=10, loc=(0, 0, -0.55*scale),
                parent=l_e, mat_=M_ZEBRA_WHITE)
            # Stripes on legs
            for sl in range(3):
                cyl(f"{name}_lst{x}{y}_{sl}", r=0.08*scale, depth=0.05*scale, segs=12,
                    loc=(0, 0, -0.25*scale - sl*0.30*scale), parent=l_e, mat_=M_ZEBRA_BLACK)
            # Hoof
            cyl(f"{name}_h{x}{y}", r=0.09*scale, depth=0.08*scale, segs=10, loc=(0, 0, -1.10*scale),
                parent=l_e, mat_=M_ZEBRA_BLACK)
    # Neck
    neck_e = empty(f"{name}_neck_e", (1.0*scale, 0, 1.2*scale), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    cyl(f"{name}_neck", r=0.20*scale, depth=0.7*scale, segs=14, loc=(0, 0, 0.35*scale),
        parent=neck_e, mat_=M_ZEBRA_WHITE)
    # Neck stripes
    for ns in range(4):
        cyl(f"{name}_nst{ns}", r=0.22*scale, depth=0.05*scale, segs=14,
            loc=(0, 0, 0.15*scale + ns*0.15*scale), parent=neck_e, mat_=M_ZEBRA_BLACK)
    # Mane
    for mn in range(8):
        beveled_cube(f"{name}_mane{mn}", (0.04*scale, 0.10*scale, 0.20*scale), bevel_offset=0.01,
                     loc=(0.05*scale, 0, 0.10*scale + mn*0.08*scale),
                     parent=neck_e, mat_=M_ZEBRA_MANE)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 0.85*scale), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.22*scale, segs=18, rings=14, loc=(0.10*scale, 0, 0),
                  parent=head_e, mat_=M_ZEBRA_WHITE, scale=(1.5, 0.9, 0.9))
    # Snout
    smooth_sphere(f"{name}_snout", r=0.15*scale, loc=(0.32*scale, 0, -0.05*scale),
                  parent=head_e, mat_=M_ZEBRA_WHITE, scale=(1.2, 0.7, 0.7))
    # Nose
    smooth_sphere(f"{name}_nose", r=0.05*scale, loc=(0.45*scale, 0, -0.02*scale),
                  parent=head_e, mat_=M_ZEBRA_BLACK)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.08*scale,
                      loc=(0, side*0.12*scale, 0.15*scale), parent=head_e,
                      mat_=M_ZEBRA_WHITE, scale=(0.5, 1, 1.2))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale,
                      loc=(0.15*scale, side*0.10*scale, 0.05*scale), parent=head_e, mat_=M_ZEBRA_BLACK)
    # Tail
    tail_e = empty(f"{name}_tail_e", (-1.0*scale, 0, 1.15*scale), parent=base)
    cyl(f"{name}_tail", r=0.04*scale, depth=0.8*scale, segs=8, loc=(0, 0, -0.40*scale),
        parent=tail_e, mat_=M_ZEBRA_WHITE)
    smooth_sphere(f"{name}_tail_t", r=0.08*scale, loc=(0, 0, -0.85*scale),
                  parent=tail_e, mat_=M_ZEBRA_MANE, scale=(0.7, 0.7, 1.5))
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e, "neck": neck_e, "tail": tail_e}

zebras = []
zebra_pos = [(10, -5, math.radians(-30)), (12, -8, math.radians(-30)),
              (8, -7, math.radians(-30)), (14, -10, math.radians(-30)),
              (10, -12, math.radians(-30)), (11, -6, math.radians(-30))]
for i, (zx, zy, fac) in enumerate(zebra_pos):
    z = make_zebra(f"zebra{i}", (zx, zy, 0), scale=1.0, facing=fac)
    zebras.append(z)

# ============ 4 GNUS / WILDEBEESTS ============
def make_gnu(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.55*scale, segs=18, rings=12, loc=(0, 0, 1.1*scale),
                  parent=base, mat_=M_GNU_DARK, scale=(1.7, 0.95, 1.0))
    # 4 legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.07*scale, depth=1.1*scale, segs=10,
                loc=(x*0.55*scale, y*0.30*scale, 0.55*scale), parent=base, mat_=M_GNU_LIGHT)
    # Beard tuft (signature gnu)
    head_e = empty(f"{name}_he", (1.0*scale, 0, 1.6*scale), parent=base)
    head_e.rotation_euler = (math.radians(-20), 0, 0)
    smooth_sphere(f"{name}_head", r=0.25*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_GNU_DARK, scale=(1.4, 0.85, 1.0))
    smooth_sphere(f"{name}_snout", r=0.17*scale, loc=(0.30*scale, 0, -0.10*scale),
                  parent=head_e, mat_=M_GNU_LIGHT, scale=(1.2, 0.8, 0.8))
    # Curved horns (signature)
    for side in (-1, 1):
        h_e = empty(f"{name}_h{side}_e", (-0.05*scale, side*0.18*scale, 0.20*scale), parent=head_e)
        h_e.rotation_euler = (0, 0, math.radians(side*30))
        for hi2 in range(3):
            cyl(f"{name}_h{side}_{hi2}", r=0.04*scale - hi2*0.005, depth=0.18*scale, segs=10,
                loc=(0, 0, hi2*0.16*scale), parent=h_e, mat_=M_TOOTH)
    # Beard
    for bd in range(5):
        cyl(f"{name}_bd{bd}", r=0.025*scale, depth=0.25*scale, segs=6,
            loc=(0.25*scale, (bd-2)*0.04*scale, -0.30*scale), parent=head_e, mat_=M_GNU_DARK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

gnus = []
gnu_pos = [(0, 0, math.radians(45)), (3, -2, math.radians(60)),
            (-2, 3, math.radians(30)), (4, 1, math.radians(50))]
for i, (gx, gy, fac) in enumerate(gnu_pos):
    g = make_gnu(f"gnu{i}", (gx, gy, 0), scale=1.0, facing=fac)
    gnus.append(g)

# ============ 4 IMPALAS ============
def make_impala(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.45*scale, segs=18, rings=12, loc=(0, 0, 1.0*scale),
                  parent=base, mat_=M_IMPALA_TAN, scale=(1.6, 0.85, 1.0))
    # White belly
    smooth_sphere(f"{name}_belly", r=0.35*scale, loc=(0, 0, 0.85*scale),
                  parent=base, mat_=M_IMPALA_WHITE, scale=(1.3, 0.7, 0.5))
    # Long thin legs
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.05*scale, depth=1.0*scale, segs=8,
                loc=(x*0.45*scale, y*0.25*scale, 0.5*scale), parent=base, mat_=M_IMPALA_TAN)
    # Neck
    neck_e = empty(f"{name}_neck_e", (0.8*scale, 0, 1.1*scale), parent=base)
    neck_e.rotation_euler = (0, math.radians(-30), 0)
    cyl(f"{name}_neck", r=0.10*scale, depth=0.5*scale, segs=10, loc=(0, 0, 0.25*scale),
        parent=neck_e, mat_=M_IMPALA_TAN)
    # Head
    head_e = empty(f"{name}_he", (0, 0, 0.7*scale), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.15*scale, segs=16, rings=12, loc=(0.10*scale, 0, 0),
                  parent=head_e, mat_=M_IMPALA_TAN, scale=(1.5, 0.85, 0.9))
    # Lyre horns (signature impala male)
    if random.random() > 0.5:
        for side in (-1, 1):
            h_e = empty(f"{name}_h{side}_e", (-0.05*scale, side*0.06*scale, 0.10*scale), parent=head_e)
            h_e.rotation_euler = (math.radians(10), 0, math.radians(side*20))
            for hi2 in range(4):
                cyl(f"{name}_h{side}_{hi2}", r=0.03*scale - hi2*0.005, depth=0.18*scale, segs=8,
                    loc=(math.sin(hi2*0.4)*0.04*scale, 0, hi2*0.16*scale), parent=h_e, mat_=M_TOOTH)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base}

impalas = []
for ii in range(4):
    impala_x = -25 + ii * 3
    impala_y = -25 + random.uniform(-3, 3)
    im = make_impala(f"impala{ii}", (impala_x, impala_y, 0),
                     scale=0.9, facing=random.uniform(0, math.pi*2))
    impalas.append(im)

# ============ 2 RHINOS ============
def make_rhino(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=0.85*scale, segs=20, rings=14, loc=(0, 0, 1.2*scale),
                  parent=base, mat_=M_RHINO_GREY, scale=(1.9, 1.0, 1.0))
    for x in (-1, 1):
        for y in (-1, 1):
            cyl(f"{name}_l{x}{y}", r=0.18*scale, depth=1.2*scale, segs=12,
                loc=(x*0.75*scale, y*0.45*scale, 0.6*scale), parent=base, mat_=M_RHINO_GREY)
    # Head
    head_e = empty(f"{name}_he", (1.4*scale, 0, 1.3*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.45*scale, segs=18, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_RHINO_GREY, scale=(1.3, 0.9, 0.9))
    # 2 horns (signature)
    smooth_cone(f"{name}_horn1", r1=0.15*scale, r2=0.04*scale, depth=0.55*scale, segs=12,
                loc=(0.40*scale, 0, 0.30*scale), parent=head_e,
                mat_=M_RHINO_HORN).rotation_euler = (0, math.radians(70), 0)
    smooth_cone(f"{name}_horn2", r1=0.10*scale, r2=0.03*scale, depth=0.30*scale, segs=12,
                loc=(0.10*scale, 0, 0.35*scale), parent=head_e,
                mat_=M_RHINO_HORN).rotation_euler = (0, math.radians(70), 0)
    # Ears
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10*scale,
                      loc=(-0.15*scale, side*0.30*scale, 0.30*scale), parent=head_e,
                      mat_=M_RHINO_GREY, scale=(0.6, 1, 1.3))
    # Eyes
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.04*scale,
                      loc=(0.20*scale, side*0.30*scale, 0.10*scale), parent=head_e, mat_=M_ZEBRA_BLACK)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "he": head_e}

rhinos = []
rhino_pos = [(-30, 10, math.radians(30)), (-32, 5, math.radians(-30))]
for i, (rx, ry, fac) in enumerate(rhino_pos):
    r = make_rhino(f"rhino{i}", (rx, ry, 0), scale=1.2, facing=fac)
    rhinos.append(r)

# ============ 4 TERMITE MOUNDS ============
for tm in range(4):
    tmx = random.uniform(-40, 40)
    tmy = random.uniform(-40, 40)
    # Avoid river area
    if 15 < tmx < 30: tmx -= 30
    tm_e = empty(f"termite{tm}", (tmx, tmy, 0))
    # Tall tapering mound
    for li in range(5):
        lz = li * 0.7
        lr = 0.7 - li*0.12
        cyl(f"tm{tm}_{li}", r=lr, depth=0.7, segs=14, loc=(0, 0, lz + 0.35),
            parent=tm_e, mat_=M_TERMITE)
    # Top spike
    smooth_cone(f"tm{tm}_top", r1=0.2, r2=0.05, depth=0.6, segs=12, loc=(0, 0, 3.8),
                parent=tm_e, mat_=M_TERMITE)

# ============ 3 HIPPOS in river ============
def make_hippo(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    smooth_sphere(f"{name}_body", r=1.0*scale, segs=20, rings=14, loc=(0, 0, 0.3*scale),
                  parent=base, mat_=M_HIPPO_GREY, scale=(1.8, 1.1, 0.7))
    # Head huge
    head_e = empty(f"{name}_he", (1.5*scale, 0, 0.4*scale), parent=base)
    smooth_sphere(f"{name}_head", r=0.75*scale, segs=20, rings=14, loc=(0, 0, 0),
                  parent=head_e, mat_=M_HIPPO_GREY, scale=(1.4, 1.1, 0.85))
    # Open mouth (signature)
    jaw_e = empty(f"{name}_jaw_e", (0.4*scale, 0, -0.30*scale), parent=head_e)
    jaw_e.rotation_euler = (math.radians(-30), 0, 0)
    smooth_sphere(f"{name}_jaw", r=0.55*scale, loc=(0.10*scale, 0, 0),
                  parent=jaw_e, mat_=M_HIPPO_PINK, scale=(1.3, 1.0, 0.4))
    # Teeth (signature 4 tusks)
    for tx in [-1, 1]:
        for ty in [-0.3, 0.3]:
            cyl(f"{name}_tk{tx}_{ty}", r=0.05*scale, depth=0.20*scale, segs=8,
                loc=(0.20*scale + tx*0.10*scale, ty*scale, 0.05*scale),
                parent=jaw_e, mat_=M_TOOTH)
    # Eyes (just visible above water)
    for side in (-1, 1):
        smooth_sphere(f"{name}_eye{side}", r=0.06*scale,
                      loc=(0.20*scale, side*0.35*scale, 0.35*scale), parent=head_e, mat_=M_LION_EYE)
    # Ears (small)
    for side in (-1, 1):
        smooth_sphere(f"{name}_ear{side}", r=0.10*scale,
                      loc=(-0.10*scale, side*0.40*scale, 0.50*scale), parent=head_e, mat_=M_HIPPO_GREY)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "jaw": jaw_e, "he": head_e}

hippos = []
hippo_pos = [(20, -10, math.radians(45)), (22, 0, math.radians(0)), (18, 15, math.radians(-30))]
for i, (hx, hy, fac) in enumerate(hippo_pos):
    h = make_hippo(f"hippo{i}", (hx, hy, 0.3), scale=1.0, facing=fac)
    hippos.append(h)

# ============ 6 FLAMINGOS pink (signature) ============
def make_flamingo(name, loc, scale=1.0, facing=0):
    base = empty(name, loc)
    base.rotation_euler = (0, 0, facing)
    # Body
    smooth_sphere(f"{name}_body", r=0.3*scale, segs=18, rings=12, loc=(0, 0, 1.2*scale),
                  parent=base, mat_=M_FLAMINGO_PINK, scale=(1.3, 0.8, 1.0))
    # Long thin legs (signature 1 leg up tucked)
    cyl(f"{name}_l1", r=0.025*scale, depth=1.2*scale, segs=8, loc=(0.05*scale, 0, 0.6*scale),
        parent=base, mat_=M_FLAMINGO_LEG)
    # Foot
    smooth_sphere(f"{name}_foot1", r=0.05*scale, loc=(0.05*scale, 0, 0),
                  parent=base, mat_=M_FLAMINGO_LEG)
    # Long sinuous neck S-curve (signature)
    neck_e = empty(f"{name}_neck_e", (0.15*scale, 0, 1.4*scale), parent=base)
    for ni in range(6):
        # S-curve via offsets
        n_x = math.sin(ni * 0.6) * 0.10 * scale
        cyl(f"{name}_neck{ni}", r=0.07*scale, depth=0.25*scale, segs=10,
            loc=(n_x, 0, ni*0.22*scale), parent=neck_e, mat_=M_FLAMINGO_PINK)
    # Head
    head_e = empty(f"{name}_he", (0.10*scale, 0, 1.4*scale), parent=neck_e)
    smooth_sphere(f"{name}_head", r=0.12*scale, segs=14, rings=10, loc=(0, 0, 0),
                  parent=head_e, mat_=M_FLAMINGO_PINK, scale=(1.2, 0.9, 1.0))
    # Curved hooked beak (signature)
    beak_e = empty(f"{name}_beak_e", (0.10*scale, 0, -0.05*scale), parent=head_e)
    beak_e.rotation_euler = (math.radians(-30), 0, 0)
    smooth_cone(f"{name}_beak", r1=0.06*scale, r2=0.01*scale, depth=0.20*scale, segs=10,
                loc=(0, 0, -0.10*scale), parent=beak_e, mat_=M_FLAMINGO_BEAK)
    # Eye
    smooth_sphere(f"{name}_eye", r=0.025*scale, loc=(0.08*scale, 0, 0.04*scale),
                  parent=head_e, mat_=M_LION_EYE)
    base["_phase"] = random.uniform(0, math.pi*2)
    return {"root": base, "neck": neck_e, "he": head_e}

flamingos = []
flamingo_pos = [(15, -25, math.radians(45)), (18, -27, math.radians(60)),
                 (12, -23, math.radians(30)), (16, -22, math.radians(120)),
                 (20, -25, math.radians(-30)), (14, -28, math.radians(90))]
for i, (fx, fy, fac) in enumerate(flamingo_pos):
    f_obj = make_flamingo(f"flamingo{i}", (fx, fy, 0), scale=1.0, facing=fac)
    flamingos.append(f_obj)

# ============ CROCODILE in river ============
croc_e = empty("crocodile", loc=(22, 30, 0.2))
# Long body
smooth_cone("croc_body", r1=0.45, r2=0.20, depth=3.5, segs=18, loc=(0, 0, 0.15),
            parent=croc_e, mat_=M_CROC_GREEN).rotation_euler = (0, math.radians(90), 0)
# Back scales (signature)
for sc in range(10):
    scx = -1.4 + sc * 0.30
    beveled_cube(f"croc_scl{sc}", (0.08, 0.20, 0.10), bevel_offset=0.02,
                 loc=(scx, 0, 0.30), parent=croc_e, mat_=M_CROC_DARK)
# Head with jaws (signature)
head_e = empty("croc_he", (1.5, 0, 0.15), parent=croc_e)
smooth_sphere("croc_head", r=0.40, segs=18, rings=14, loc=(0.20, 0, 0), parent=head_e,
              mat_=M_CROC_GREEN, scale=(1.5, 0.85, 0.55))
# Eyes (raised signature)
for side in (-1, 1):
    smooth_sphere(f"croc_eye_b{side}", r=0.10, loc=(0.10, side*0.20, 0.25),
                  parent=head_e, mat_=M_CROC_GREEN)
    smooth_sphere(f"croc_eye{side}", r=0.05, loc=(0.10, side*0.20, 0.32),
                  parent=head_e, mat_=M_CROC_EYE)
# Teeth row
for tt in range(8):
    cyl(f"croc_tt{tt}", r=0.025, depth=0.10, segs=6,
        loc=(0.10 + (tt-3.5)*0.10, 0.22, 0), parent=head_e, mat_=M_TOOTH)
    cyl(f"croc_tt_b{tt}", r=0.025, depth=0.10, segs=6,
        loc=(0.10 + (tt-3.5)*0.10, -0.22, 0), parent=head_e, mat_=M_TOOTH)
# Long tail
tail_e = empty("croc_tail", (-1.8, 0, 0.15), parent=croc_e)
for ti2 in range(6):
    cyl(f"croc_t{ti2}", r=0.30 - ti2*0.04, depth=0.40, segs=14, loc=(-ti2*0.40, 0, 0),
        parent=tail_e, mat_=M_CROC_GREEN).rotation_euler = (0, math.radians(90), 0)

# ============================================================
# ⭐ 600 DUST + 400 EXOTIC BIRDS (PARTICULES THÉMATIQUES OBLIGATOIRES)
# ============================================================
dust_particles = []
for i in range(600):
    px = random.uniform(-50, 50)
    py = random.uniform(-50, 50)
    pz = random.uniform(0.5, 8)
    s_obj = smooth_sphere(f"dust{i}", r=random.uniform(0.05, 0.10), segs=8, rings=6,
                          loc=(px, py, pz), mat_=M_DUST)
    s_obj["_phase"] = random.uniform(0, math.pi*2)
    s_obj["_base_x"] = px; s_obj["_base_y"] = py; s_obj["_base_z"] = pz
    s_obj["_amp_x"] = random.uniform(0.8, 2.0)
    s_obj["_amp_y"] = random.uniform(0.8, 2.0)
    s_obj["_amp_z"] = random.uniform(0.3, 1.0)
    s_obj["_speed"] = random.uniform(0.2, 0.6)
    dust_particles.append(s_obj)

# 400 exotic birds
exotic_birds = []
for i in range(400):
    px = random.uniform(-55, 55)
    py = random.uniform(-55, 55)
    pz = random.uniform(2, 18)
    bird_e = empty(f"bird{i}", (px, py, pz))
    bird_color = random.choice(BIRD_COLORS)
    # Body
    smooth_sphere(f"b_body{i}", r=0.10, segs=10, rings=6, loc=(0, 0, 0),
                  parent=bird_e, mat_=bird_color, scale=(1.4, 1, 0.9))
    # Wings
    for side in (-1, 1):
        wing = beveled_cube(f"b_w{i}_{side}", (0.05, 0.20, 0.04), bevel_offset=0.01,
                            loc=(0, side*0.12, 0), parent=bird_e, mat_=bird_color)
    # Beak
    smooth_cone(f"b_bk{i}", r1=0.03, r2=0.005, depth=0.10, segs=8,
                loc=(0.10, 0, 0), parent=bird_e, mat_=M_BIRD_BK).rotation_euler = (0, math.radians(90), 0)
    bird_e["_phase"] = random.uniform(0, math.pi*2)
    bird_e["_base_x"] = px; bird_e["_base_y"] = py; bird_e["_base_z"] = pz
    bird_e["_amp_x"] = random.uniform(2.5, 5.0)
    bird_e["_amp_y"] = random.uniform(2.5, 5.0)
    bird_e["_amp_z"] = random.uniform(0.8, 2.0)
    bird_e["_speed"] = random.uniform(0.8, 1.8)
    exotic_birds.append(bird_e)

# ============ ANIMATION ============
fps = 30; duration_s = 6; total_frames = fps * duration_s

# Acacias sway in wind
for ac in acacias:
    phase = ac["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        ac.rotation_euler = (math.sin(t * 0.5 + phase) * math.radians(3),
                              math.cos(t * 0.5 + phase) * math.radians(3), 0)
        ac.keyframe_insert("rotation_euler", frame=f)

# Giraffes walk legs + neck sway + tail
for g in giraffes:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body
        g["root"].location.z = abs(math.sin(t * 1.5 + phase)) * 0.08
        g["root"].keyframe_insert("location", frame=f)
        # Neck sway
        g["neck"].rotation_euler = (0, math.radians(-30) + math.sin(t * 1.0 + phase) * math.radians(8),
                                     math.cos(t * 1.0 + phase) * math.radians(10))
        g["neck"].keyframe_insert("rotation_euler", frame=f)
        # Head turn
        g["he"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(15))
        g["he"].keyframe_insert("rotation_euler", frame=f)
        # Tail swing
        g["tail"].rotation_euler = (0, math.sin(t * 3.0 + phase) * math.radians(20), 0)
        g["tail"].keyframe_insert("rotation_euler", frame=f)
        # Legs walking
        for li, leg in enumerate(g["legs"]):
            leg.rotation_euler = (math.sin(t * 2.5 + phase + li*0.7) * math.radians(15), 0, 0)
            leg.keyframe_insert("rotation_euler", frame=f)

# Lions roar (jaw open close) + body breath + tail swish
for li, l in enumerate(lions):
    phase = l["root"]["_phase"]
    is_male = (li == 0)
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body breath
        l["root"].location.z = math.sin(t * 1.5 + phase) * 0.05
        l["root"].keyframe_insert("location", frame=f)
        # Tail swish
        l["tail"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(20),
                                     math.cos(t * 1.5 + phase) * math.radians(15),
                                     math.radians(45))
        l["tail"].keyframe_insert("rotation_euler", frame=f)
        # Jaw roar (male)
        if is_male:
            l["jaw"].rotation_euler = (math.sin(t * 0.8 + phase) * math.radians(15), 0, 0)
            l["jaw"].keyframe_insert("rotation_euler", frame=f)

# Elephants trunk waving + tail
for e in elephants:
    phase = e["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        # Body sway
        e["root"].rotation_euler = (0, math.sin(t * 0.6 + phase) * math.radians(3),
                                     e["root"].rotation_euler.z)
        e["root"].keyframe_insert("rotation_euler", frame=f)
        # Trunk wave (signature)
        e["trunk"].rotation_euler = (math.radians(20) + math.sin(t * 1.5 + phase) * math.radians(15),
                                      math.cos(t * 1.5 + phase) * math.radians(10),
                                      math.sin(t * 1.0 + phase) * math.radians(8))
        e["trunk"].keyframe_insert("rotation_euler", frame=f)
        # Tail
        e["tail"].rotation_euler = (math.sin(t * 2.0 + phase) * math.radians(25), 0, 0)
        e["tail"].keyframe_insert("rotation_euler", frame=f)
        # Head nod
        e["he"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(5), 0, 0)
        e["he"].keyframe_insert("rotation_euler", frame=f)

# Zebras gallop
for z in zebras:
    phase = z["root"]["_phase"]
    bx_z = z["root"].location.x; by_z = z["root"].location.y
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        z["root"].location.x = bx_z + math.sin(t * 2.0 + phase) * 0.5
        z["root"].location.y = by_z + math.cos(t * 2.0 + phase) * 0.5
        z["root"].location.z = abs(math.sin(t * 4.0 + phase)) * 0.20
        z["root"].keyframe_insert("location", frame=f)
        # Neck up/down
        z["neck"].rotation_euler = (0, math.radians(-30) + math.sin(t * 4.0 + phase) * math.radians(8), 0)
        z["neck"].keyframe_insert("rotation_euler", frame=f)
        # Tail
        z["tail"].rotation_euler = (math.sin(t * 5.0 + phase) * math.radians(25), 0, 0)
        z["tail"].keyframe_insert("rotation_euler", frame=f)

# Gnus head sway
for g in gnus:
    phase = g["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        g["he"].rotation_euler = (math.radians(-20) + math.sin(t * 1.5 + phase) * math.radians(10),
                                   0, math.cos(t * 1.5 + phase) * math.radians(15))
        g["he"].keyframe_insert("rotation_euler", frame=f)

# Impalas bounce
for im in impalas:
    phase = im["root"]["_phase"]
    bx_i = im["root"].location.x; by_i = im["root"].location.y
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        im["root"].location.z = abs(math.sin(t * 3.0 + phase)) * 0.6
        im["root"].location.x = bx_i + math.sin(t * 1.5 + phase) * 0.8
        im["root"].location.y = by_i + math.cos(t * 1.5 + phase) * 0.8
        im["root"].keyframe_insert("location", frame=f)

# Rhinos head turn
for rh in rhinos:
    phase = rh["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        rh["he"].rotation_euler = (0, 0, math.sin(t * 0.8 + phase) * math.radians(10))
        rh["he"].keyframe_insert("rotation_euler", frame=f)

# Hippos jaw open/close
for hp in hippos:
    phase = hp["root"]["_phase"]
    for f in range(1, total_frames + 1, 4):
        t = (f - 1) / fps
        hp["jaw"].rotation_euler = (math.radians(-30) + abs(math.sin(t * 1.0 + phase)) * math.radians(40), 0, 0)
        hp["jaw"].keyframe_insert("rotation_euler", frame=f)
        hp["root"].location.z = 0.3 + math.sin(t * 0.8 + phase) * 0.05
        hp["root"].keyframe_insert("location", frame=f)

# Flamingos neck S-curve + slight body
for fl in flamingos:
    phase = fl["root"]["_phase"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        fl["neck"].rotation_euler = (math.sin(t * 1.0 + phase) * math.radians(5),
                                      math.cos(t * 1.0 + phase) * math.radians(5),
                                      math.sin(t * 0.8 + phase) * math.radians(15))
        fl["neck"].keyframe_insert("rotation_euler", frame=f)
        fl["he"].rotation_euler = (0, 0, math.sin(t * 1.2 + phase) * math.radians(20))
        fl["he"].keyframe_insert("rotation_euler", frame=f)

# Sun slow descent
for f in range(1, total_frames + 1, 6):
    t = (f - 1) / fps
    sun_e.location.z = 12 - t * 0.3
    sun_e.keyframe_insert("location", frame=f)

# 600 dust particles drift
for d in dust_particles:
    phase = d["_phase"]; speed = d["_speed"]
    bx, by, bz = d["_base_x"], d["_base_y"], d["_base_z"]
    ax, ay, az = d["_amp_x"], d["_amp_y"], d["_amp_z"]
    for f in range(1, total_frames + 1, 5):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase)
        y = by + ay * math.cos(t * speed * 0.9 + phase)
        z = bz + az * math.sin(t * speed * 1.3 + phase)
        d.location = (x, y, max(0.3, z))
        d.keyframe_insert("location", frame=f)

# 400 exotic birds erratic flight + wing flap
for bd in exotic_birds:
    phase = bd["_phase"]; speed = bd["_speed"]
    bx, by, bz = bd["_base_x"], bd["_base_y"], bd["_base_z"]
    ax, ay, az = bd["_amp_x"], bd["_amp_y"], bd["_amp_z"]
    for f in range(1, total_frames + 1, 3):
        t = (f - 1) / fps
        x = bx + ax * math.sin(t * speed + phase) + 0.5*math.sin(t * speed * 3 + phase * 2)
        y = by + ay * math.cos(t * speed * 0.9 + phase) + 0.5*math.cos(t * speed * 3 + phase)
        z = bz + az * math.sin(t * speed * 1.4 + phase) + 0.3*math.sin(t * 4.0 + phase)
        bd.location = (x, y, max(1, z))
        bd.rotation_euler = (math.sin(t * 8.0 + phase) * 0.3,
                              math.cos(t * 8.0 + phase) * 0.3,
                              math.atan2(math.cos(t * speed * 0.9 + phase),
                                         math.sin(t * speed + phase)))
        bd.keyframe_insert("location", frame=f)
        bd.keyframe_insert("rotation_euler", frame=f)

# ============ EXPORT ============
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "_pbr_test")
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_glb = os.path.join(out_dir, "pbr_safari_proc.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format='GLB',
    export_animations=True, export_apply=False, export_yup=True, use_selection=False,
)
size_mb = os.path.getsize(out_glb) / (1024 * 1024)
print(f"[proc_african_savanna_safari_acacia] DONE → {out_glb} ({size_mb:.2f} MB)")
print(f"[proc_african_savanna_safari_acacia] savanna + 5 acacias + 4 giraffes + 6 lions (male+females+cubs) + 8 elephants + 6 zebras + 4 gnus + 4 impalas + 2 rhinos + 4 termite mounds + river + 3 hippos + 6 flamingos + crocodile + 600 dust + 400 birds")
print("⭐ FIXES: 1 ground + 600 dust + 400 exotic birds (signature savanna thematic mandatory) ⭐")
