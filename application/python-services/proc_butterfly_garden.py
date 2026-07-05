"""
proc_butterfly_garden.py — 157e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Jardin enchanté avec 8 papillons et faune jardin :
- 8 papillons couleurs distinctes : corps articulé 3 segments + 2 antennes + 4 ailes (2 sup + 2 inf) flap synchronisé L/R + yeux émissifs
- 20 fleurs variées 5 sortes (rose, tournesol, marguerite, tulipe, orchidée) sur tiges feuilles
- 6 abeilles bourdonnant (corps rayé + 4 ailes flap rapide)
- 4 libellules darting (corps long + 4 ailes + queue)
- 15 brins d'herbe sway
- fontaine centrale émissive + 6 jets + bassin
- 3 lily pads + 3 nénuphars
- nuage pollen émissif 60 particules
- soleil émissif chaud + 3 halos
- ciel bleu pastel
- 4 nuages duveteux

Animations multi-axes simultanées :
- 8 papillons orbites 3D différentielles (radius/y/speed unique) + bank + flap rapide
- 4 ailes par papillon flap synchronisé L/R (sup vs inf phase shift)
- 20 fleurs : pulse émission scale gentle
- 6 abeilles bourdonnent autour fleurs (orbits courts + 4 wings flap super rapide)
- 4 libellules darting (mouvements saccadés + 4 ailes flap)
- 15 brins d'herbe sway X+Z phase chacune
- fontaine 6 jets rise cyclique
- 60 pollen drift 3D + scintille
- soleil pulse + halos breathe

Sortie : output/3d/pbr_butterfly_proc.glb.
"""
import bmesh
import bpy
import math
import os
import random

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 180
scene.render.fps = 30

CWD = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_butterfly_proc.glb"))

random.seed(0xBEEF15)


def make_mat(name, base, metallic=0.0, roughness=0.6, alpha=1.0, emi=(0, 0, 0), emi_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Alpha"].default_value = alpha
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*emi, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = emi_strength
    if alpha < 1.0:
        mat.blend_method = 'BLEND'
    return mat


def add_obj(name, mesh, parent=None):
    o = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(o)
    if parent:
        o.parent = parent
    return o


def empty(name, location=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.location = location
    scene.collection.objects.link(e)
    if parent:
        e.parent = parent
    return e


def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(size_xyz[0], size_xyz[1], size_xyz[2]), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=bevel_offset, segments=bevel_segments, profile=0.5, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


def smooth_sphere(name, r=1.0, segs=32, rings=20, loc=(0, 0, 0), parent=None, mat=None, scale=(1, 1, 1)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    if scale != (1, 1, 1):
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


def smooth_cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY = make_mat("sky_pastel", (0.55, 0.75, 0.95), roughness=1.0, emi=(0.35, 0.50, 0.70), emi_strength=0.6)
MAT_SUN = make_mat("sun", (1.0, 0.95, 0.65), roughness=0.0, emi=(1.0, 0.95, 0.65), emi_strength=10.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.95, 0.65), roughness=0.0, alpha=0.30, emi=(1.0, 0.95, 0.65), emi_strength=3.0)
MAT_CLOUD = make_mat("cloud", (0.98, 0.98, 0.98), roughness=1.0, alpha=0.65, emi=(0.55, 0.55, 0.55), emi_strength=0.3)
MAT_GRASS = make_mat("grass", (0.30, 0.65, 0.25), roughness=0.7, emi=(0.10, 0.30, 0.10), emi_strength=0.3)
MAT_GRASS_LIGHT = make_mat("grass_light", (0.55, 0.85, 0.40), roughness=0.55, emi=(0.20, 0.40, 0.15), emi_strength=0.4)
MAT_GRASS_BLADE = make_mat("grass_blade", (0.45, 0.75, 0.30), roughness=0.6)
MAT_STEM = make_mat("stem", (0.20, 0.50, 0.15), roughness=0.7)
MAT_LEAF = make_mat("leaf", (0.25, 0.55, 0.18), roughness=0.6, emi=(0.10, 0.25, 0.08), emi_strength=0.3)
MAT_PETAL_ROSE = make_mat("petal_rose", (0.95, 0.30, 0.55), roughness=0.4, emi=(0.45, 0.10, 0.20), emi_strength=0.6)
MAT_PETAL_SUNFLOWER = make_mat("petal_sun", (1.0, 0.80, 0.20), roughness=0.4, emi=(0.50, 0.40, 0.10), emi_strength=0.6)
MAT_PETAL_DAISY = make_mat("petal_daisy", (1.0, 1.0, 0.95), roughness=0.4, emi=(0.40, 0.40, 0.35), emi_strength=0.4)
MAT_PETAL_TULIP = make_mat("petal_tulip", (0.95, 0.25, 0.25), roughness=0.4, emi=(0.45, 0.10, 0.10), emi_strength=0.6)
MAT_PETAL_ORCHID = make_mat("petal_orchid", (0.85, 0.45, 1.0), roughness=0.4, emi=(0.40, 0.20, 0.55), emi_strength=0.7)
MAT_PETAL_CENTER = make_mat("petal_center", (0.55, 0.30, 0.10), roughness=0.5, emi=(0.25, 0.15, 0.05), emi_strength=0.3)
MAT_BUTTERFLY_BODY = make_mat("but_body", (0.15, 0.10, 0.08), roughness=0.5)
MAT_BUTTERFLY_EYE = make_mat("but_eye", (1.0, 0.85, 0.20), roughness=0.0, emi=(1.0, 0.85, 0.20), emi_strength=8.0)
MAT_WING_A = make_mat("wing_A", (0.95, 0.30, 0.30), roughness=0.3, alpha=0.90, emi=(0.50, 0.10, 0.10), emi_strength=1.0)
MAT_WING_B = make_mat("wing_B", (0.30, 0.45, 0.95), roughness=0.3, alpha=0.90, emi=(0.10, 0.20, 0.50), emi_strength=1.0)
MAT_WING_C = make_mat("wing_C", (1.0, 0.65, 0.20), roughness=0.3, alpha=0.90, emi=(0.50, 0.30, 0.10), emi_strength=1.0)
MAT_WING_D = make_mat("wing_D", (0.85, 0.30, 0.95), roughness=0.3, alpha=0.90, emi=(0.40, 0.10, 0.50), emi_strength=1.0)
MAT_WING_E = make_mat("wing_E", (0.30, 0.85, 0.55), roughness=0.3, alpha=0.90, emi=(0.10, 0.45, 0.25), emi_strength=1.0)
MAT_WING_F = make_mat("wing_F", (1.0, 0.95, 0.40), roughness=0.3, alpha=0.90, emi=(0.55, 0.50, 0.15), emi_strength=1.0)
MAT_WING_G = make_mat("wing_G", (0.95, 0.55, 0.85), roughness=0.3, alpha=0.90, emi=(0.50, 0.25, 0.45), emi_strength=1.0)
MAT_WING_H = make_mat("wing_H", (0.50, 0.95, 0.95), roughness=0.3, alpha=0.90, emi=(0.20, 0.50, 0.50), emi_strength=1.0)
MAT_BEE_BODY = make_mat("bee_body", (1.0, 0.85, 0.10), roughness=0.5, emi=(0.40, 0.30, 0.05), emi_strength=0.5)
MAT_BEE_STRIPE = make_mat("bee_stripe", (0.15, 0.10, 0.05), roughness=0.6)
MAT_BEE_WING = make_mat("bee_wing", (0.95, 0.95, 1.0), roughness=0.10, alpha=0.45, emi=(0.50, 0.50, 0.60), emi_strength=1.0)
MAT_DRAGONFLY = make_mat("dragonfly", (0.20, 0.85, 0.95), roughness=0.4, emi=(0.10, 0.40, 0.50), emi_strength=1.5)
MAT_DRAGONFLY_WING = make_mat("dragonfly_wing", (0.85, 0.95, 1.0), roughness=0.10, alpha=0.50, emi=(0.40, 0.50, 0.55), emi_strength=1.5)
MAT_FOUNTAIN_STONE = make_mat("fountain_stone", (0.65, 0.62, 0.58), roughness=0.7)
MAT_WATER = make_mat("water", (0.40, 0.75, 0.95), roughness=0.15, alpha=0.55, emi=(0.20, 0.50, 0.70), emi_strength=2.0)
MAT_LILY = make_mat("lily", (0.20, 0.55, 0.25), roughness=0.7, emi=(0.05, 0.20, 0.08), emi_strength=0.3)
MAT_LOTUS = make_mat("lotus", (0.95, 0.80, 0.95), roughness=0.4, emi=(0.45, 0.30, 0.45), emi_strength=0.5)
MAT_POLLEN_A = make_mat("pollen_A", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=6.0)
MAT_POLLEN_B = make_mat("pollen_B", (1.0, 1.0, 0.65), roughness=0.0, emi=(1.0, 1.0, 0.65), emi_strength=6.0)


# --- backdrop : sky + ground -----------------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, 13, 8), mat=MAT_SKY)
ground = beveled_cube("ground", (30, 0.2, 20), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GRASS)
# 2 grass patches lighter
for gx, gz in [(-5, 4), (6, 5)]:
    smooth_sphere(f"grass_patch_{gx}", r=2.0, segs=18, rings=10, loc=(gx, 0.05, gz), mat=MAT_GRASS_LIGHT, scale=(1.0, 0.10, 1.0))

# sun + halos
sun_p = empty("sun_p", (10, 11, 7))
sun = smooth_sphere("sun", r=1.1, segs=28, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=1.8, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=2.5, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_3 = smooth_sphere("sun_halo_3", r=3.2, segs=18, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# 4 fluffy clouds
clouds = []
for ck in range(4):
    cx = random.uniform(-12, 12)
    cz = random.uniform(4, 9)
    cy = random.uniform(8, 11)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    for j in range(4):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.7, 1.05), segs=18, rings=12, loc=(random.uniform(-0.9, 0.9), random.uniform(-0.15, 0.20), random.uniform(-0.6, 0.6)), parent=cp, mat=MAT_CLOUD, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.4, 0.8)


# --- fountain centrale + bassin --------------------------------------------
fount_p = empty("fountain", (0, 0, 1))
# bassin (large flat torus)
basin = smooth_cone("basin", r1=2.2, r2=2.0, depth=0.4, segs=28, loc=(0, 0.20, 0), parent=fount_p, mat=MAT_FOUNTAIN_STONE)
# water surface
water_surf = smooth_cone("water_surf", r1=2.0, r2=2.0, depth=0.05, segs=28, loc=(0, 0.40, 0), parent=fount_p, mat=MAT_WATER)
# central pillar
pillar = smooth_cone("fount_pillar", r1=0.30, r2=0.25, depth=1.4, segs=14, loc=(0, 1.10, 0), parent=fount_p, mat=MAT_FOUNTAIN_STONE)
# decorative top
fount_top = smooth_sphere("fount_top", r=0.40, segs=18, rings=12, loc=(0, 1.95, 0), parent=fount_p, mat=MAT_FOUNTAIN_STONE)
# 6 water jets émissif
jets = []
for jk in range(6):
    ja = jk * (math.pi * 2 / 6)
    jp = empty(f"jet_{jk}", (math.cos(ja) * 0.30, 2.10, math.sin(ja) * 0.30), parent=fount_p)
    jet_seg = smooth_cone(f"jet_{jk}_b", r1=0.06, r2=0.04, depth=0.80, segs=8, loc=(0, 0.40, 0), parent=jp, mat=MAT_WATER)
    jet_seg.rotation_euler = (math.radians(15 * math.cos(ja)), 0, math.radians(15 * math.sin(ja)))
    jp["_phase"] = jk * 0.20
    jets.append(jp)

# 3 lily pads + 3 lotus on water surface
for lk in range(3):
    la = lk * (math.pi * 2 / 3) + 0.5
    lr = 1.5
    lx = math.cos(la) * lr
    lz = math.sin(la) * lr
    # pad (flat sphere)
    smooth_sphere(f"lily_{lk}", r=0.40, segs=16, rings=8, loc=(lx, 0.43, lz), parent=fount_p, mat=MAT_LILY, scale=(1.0, 0.10, 1.0))
    # lotus flower
    for pt in range(5):
        pa = pt * (math.pi * 2 / 5)
        smooth_cone(f"lotus_{lk}_p_{pt}", r1=0.08, r2=0.0, depth=0.20, segs=10, loc=(lx + math.cos(pa) * 0.10, 0.55, lz + math.sin(pa) * 0.10), parent=fount_p, mat=MAT_LOTUS)


# --- 20 fleurs variées sur tiges --------------------------------------------
FLOWER_TYPES = ['rose', 'sun', 'daisy', 'tulip', 'orchid']
flowers = []
for fk in range(20):
    # spread around fountain but not too close
    a = fk * (math.pi * 2 / 20) + random.uniform(-0.1, 0.1)
    r = random.uniform(3.5, 7.0)
    fx = math.cos(a) * r
    fz = math.sin(a) * r
    if 0 < fz < 2 and abs(fx) < 2:
        fx += 3 * (1 if fx >= 0 else -1)
    ft = FLOWER_TYPES[fk % 5]
    h = random.uniform(0.9, 1.6)
    fp = empty(f"flower_{fk}", (fx, 0, fz))
    flowers.append(fp)
    # stem
    smooth_cone(f"flower_{fk}_stem", r1=0.04, r2=0.03, depth=h, segs=8, loc=(0, h / 2, 0), parent=fp, mat=MAT_STEM)
    # 2 leaves
    for lf in range(2):
        leaf_p = empty(f"flower_{fk}_leaf_p_{lf}", (0, h * 0.4 + lf * 0.20, 0), parent=fp)
        leaf_p.rotation_euler = (0, math.radians(lf * 180), 0)
        leaf = smooth_sphere(f"flower_{fk}_leaf_{lf}", r=0.18, segs=12, rings=8, loc=(0.12, 0, 0), parent=leaf_p, mat=MAT_LEAF, scale=(1.0, 0.10, 0.45))
    # flower head
    if ft == 'rose':
        # 8 petals layered
        for pi in range(8):
            pa = pi * (math.pi * 2 / 8)
            smooth_sphere(f"flower_{fk}_pet_{pi}", r=0.10, segs=12, rings=8, loc=(math.cos(pa) * 0.06, h + 0.08, math.sin(pa) * 0.06), parent=fp, mat=MAT_PETAL_ROSE, scale=(1.0, 0.4, 0.5))
        center = smooth_sphere(f"flower_{fk}_ctr", r=0.06, segs=12, rings=8, loc=(0, h + 0.08, 0), parent=fp, mat=MAT_PETAL_CENTER)
    elif ft == 'sun':
        # 12 long petals + dark center
        for pi in range(12):
            pa = pi * (math.pi * 2 / 12)
            smooth_cone(f"flower_{fk}_pet_{pi}", r1=0.06, r2=0.0, depth=0.18, segs=8, loc=(math.cos(pa) * 0.18, h + 0.02, math.sin(pa) * 0.18), parent=fp, mat=MAT_PETAL_SUNFLOWER)
        center = smooth_sphere(f"flower_{fk}_ctr", r=0.15, segs=16, rings=10, loc=(0, h + 0.02, 0), parent=fp, mat=MAT_PETAL_CENTER, scale=(1.0, 0.5, 1.0))
    elif ft == 'daisy':
        # 10 white petals + yellow center
        for pi in range(10):
            pa = pi * (math.pi * 2 / 10)
            smooth_sphere(f"flower_{fk}_pet_{pi}", r=0.10, segs=10, rings=6, loc=(math.cos(pa) * 0.14, h + 0.02, math.sin(pa) * 0.14), parent=fp, mat=MAT_PETAL_DAISY, scale=(1.4, 0.20, 0.6))
        center = smooth_sphere(f"flower_{fk}_ctr", r=0.08, segs=14, rings=8, loc=(0, h + 0.04, 0), parent=fp, mat=MAT_PETAL_SUNFLOWER)
    elif ft == 'tulip':
        # 6 upward petals forming cup
        for pi in range(6):
            pa = pi * (math.pi * 2 / 6)
            tp = smooth_cone(f"flower_{fk}_pet_{pi}", r1=0.10, r2=0.05, depth=0.22, segs=8, loc=(math.cos(pa) * 0.08, h + 0.10, math.sin(pa) * 0.08), parent=fp, mat=MAT_PETAL_TULIP)
            tp.rotation_euler = (math.radians(20 * math.cos(pa)), 0, math.radians(20 * math.sin(pa)))
    elif ft == 'orchid':
        # 5 elongated petals + center
        for pi in range(5):
            pa = pi * (math.pi * 2 / 5)
            smooth_sphere(f"flower_{fk}_pet_{pi}", r=0.10, segs=12, rings=8, loc=(math.cos(pa) * 0.10, h + 0.05, math.sin(pa) * 0.10), parent=fp, mat=MAT_PETAL_ORCHID, scale=(1.5, 0.25, 0.7))
        smooth_sphere(f"flower_{fk}_ctr", r=0.06, segs=12, rings=8, loc=(0, h + 0.05, 0), parent=fp, mat=MAT_PETAL_CENTER)
    fp["_phase"] = fk * 0.3


# --- 15 grass blades sway --------------------------------------------------
grass_blades = []
for gk in range(15):
    gx = random.uniform(-9, 9)
    gz = random.uniform(-2, 7)
    if abs(gx) < 3 and abs(gz - 1) < 3:
        continue  # skip near fountain
    gp = empty(f"grass_{gk}", (gx, 0, gz))
    grass_blades.append(gp)
    # 3 blades cluster
    for bb in range(3):
        ba = bb * (math.pi * 2 / 3) + random.uniform(-0.3, 0.3)
        h = random.uniform(0.40, 0.70)
        smooth_cone(f"grass_{gk}_b_{bb}", r1=0.04, r2=0.0, depth=h, segs=6, loc=(math.cos(ba) * 0.05, h / 2, math.sin(ba) * 0.05), parent=gp, mat=MAT_GRASS_BLADE)


# --- 8 BUTTERFLIES ---------------------------------------------------------
WING_COLORS = [MAT_WING_A, MAT_WING_B, MAT_WING_C, MAT_WING_D, MAT_WING_E, MAT_WING_F, MAT_WING_G, MAT_WING_H]
butterflies = []
for bk in range(8):
    bp = empty(f"butterfly_{bk}_p", (0, 4, 0))
    # body : 3 segments
    for sg in range(3):
        rb = 0.10 - sg * 0.02
        smooth_sphere(f"but_{bk}_body_{sg}", r=rb, segs=14, rings=10, loc=(0.10 * (sg - 1), 0, 0), parent=bp, mat=MAT_BUTTERFLY_BODY, scale=(1.4, 1.0, 0.9))
    # 2 antennae
    for ak, az in [("L", 0.05), ("R", -0.05)]:
        ant = smooth_cone(f"but_{bk}_ant_{ak}", r1=0.012, r2=0.0, depth=0.18, segs=6, loc=(0.15, 0.06, az), parent=bp, mat=MAT_BUTTERFLY_BODY)
        ant.rotation_euler = (0, 0, math.radians(45))
        # tip ball
        smooth_sphere(f"but_{bk}_ant_tip_{ak}", r=0.022, segs=10, rings=6, loc=(0.27, 0.18, az), parent=bp, mat=MAT_BUTTERFLY_EYE)
    # 2 eyes
    for ek, ez in [("L", 0.05), ("R", -0.05)]:
        smooth_sphere(f"but_{bk}_eye_{ek}", r=0.035, segs=10, rings=8, loc=(0.13, 0.03, ez), parent=bp, mat=MAT_BUTTERFLY_EYE)

    # 4 wings : 2 upper + 2 lower, on hinges
    wing_mat = WING_COLORS[bk]
    wing_L_p = empty(f"but_{bk}_wL", (0, 0, 0.05), parent=bp)
    wing_R_p = empty(f"but_{bk}_wR", (0, 0, -0.05), parent=bp)
    # upper wing L
    upper_L = smooth_sphere(f"but_{bk}_uL", r=0.30, segs=18, rings=12, loc=(0.05, 0, 0.30), parent=wing_L_p, mat=wing_mat, scale=(1.8, 0.05, 1.6))
    # lower wing L
    lower_L = smooth_sphere(f"but_{bk}_dL", r=0.22, segs=16, rings=10, loc=(-0.10, 0, 0.25), parent=wing_L_p, mat=wing_mat, scale=(1.4, 0.05, 1.5))
    # upper wing R
    upper_R = smooth_sphere(f"but_{bk}_uR", r=0.30, segs=18, rings=12, loc=(0.05, 0, -0.30), parent=wing_R_p, mat=wing_mat, scale=(1.8, 0.05, 1.6))
    # lower wing R
    lower_R = smooth_sphere(f"but_{bk}_dR", r=0.22, segs=16, rings=10, loc=(-0.10, 0, -0.25), parent=wing_R_p, mat=wing_mat, scale=(1.4, 0.05, 1.5))

    # orbit parameters
    orbit_r = random.uniform(3.5, 7.0)
    orbit_y = random.uniform(2.5, 5.5)
    spd = random.choice([-1, 1]) * random.uniform(0.4, 0.8)
    phase = bk * 0.5
    butterflies.append({
        "p": bp, "wL": wing_L_p, "wR": wing_R_p,
        "orbit_r": orbit_r, "orbit_y": orbit_y, "spd": spd, "phase": phase,
    })


# --- 6 BEES bourdonnant ---------------------------------------------------
bees = []
for bk in range(6):
    # target = random flower
    target_idx = bk % 20
    target = flowers[target_idx]
    tx, ty, tz = target.location.x, target.location.y + 1.2, target.location.z
    bp = empty(f"bee_{bk}_p", (tx, ty, tz))
    # body 2 segments
    for sg in range(2):
        col = MAT_BEE_BODY if sg == 0 else MAT_BEE_STRIPE
        smooth_sphere(f"bee_{bk}_body_{sg}", r=0.06, segs=12, rings=8, loc=(0.05 * (sg - 0.5), 0, 0), parent=bp, mat=col, scale=(1.0, 1.0, 1.0))
    # 4 wings (2 upper + 2 lower)
    wing_L_e = empty(f"bee_{bk}_wL", (0, 0.02, 0.04), parent=bp)
    wing_R_e = empty(f"bee_{bk}_wR", (0, 0.02, -0.04), parent=bp)
    smooth_sphere(f"bee_{bk}_wuL", r=0.08, segs=10, rings=6, loc=(0, 0.02, 0.10), parent=wing_L_e, mat=MAT_BEE_WING, scale=(1.0, 0.05, 1.5))
    smooth_sphere(f"bee_{bk}_wdL", r=0.06, segs=10, rings=6, loc=(-0.04, 0.02, 0.08), parent=wing_L_e, mat=MAT_BEE_WING, scale=(0.9, 0.05, 1.3))
    smooth_sphere(f"bee_{bk}_wuR", r=0.08, segs=10, rings=6, loc=(0, 0.02, -0.10), parent=wing_R_e, mat=MAT_BEE_WING, scale=(1.0, 0.05, 1.5))
    smooth_sphere(f"bee_{bk}_wdR", r=0.06, segs=10, rings=6, loc=(-0.04, 0.02, -0.08), parent=wing_R_e, mat=MAT_BEE_WING, scale=(0.9, 0.05, 1.3))
    bees.append({"p": bp, "wL": wing_L_e, "wR": wing_R_e, "tx": tx, "ty": ty, "tz": tz, "phase": bk * 0.4})


# --- 4 DRAGONFLIES darting ------------------------------------------------
dragonflies = []
for dk in range(4):
    dp = empty(f"dragonfly_{dk}_p", (random.uniform(-6, 6), random.uniform(2.5, 5), random.uniform(-2, 5)))
    # body long
    smooth_sphere(f"df_{dk}_body", r=0.05, segs=10, rings=6, loc=(0, 0, 0), parent=dp, mat=MAT_DRAGONFLY, scale=(3.0, 1.0, 1.0))
    # tail (elongated)
    smooth_cone(f"df_{dk}_tail", r1=0.04, r2=0.01, depth=0.35, segs=8, loc=(-0.20, 0, 0), parent=dp, mat=MAT_DRAGONFLY)
    # eyes
    for ez in [0.03, -0.03]:
        smooth_sphere(f"df_{dk}_eye", r=0.025, segs=8, rings=6, loc=(0.13, 0.025, ez), parent=dp, mat=MAT_BUTTERFLY_EYE)
    # 4 wings
    wing_L_e = empty(f"df_{dk}_wL", (0, 0, 0.04), parent=dp)
    wing_R_e = empty(f"df_{dk}_wR", (0, 0, -0.04), parent=dp)
    smooth_sphere(f"df_{dk}_wuL", r=0.18, segs=12, rings=6, loc=(0.04, 0, 0.20), parent=wing_L_e, mat=MAT_DRAGONFLY_WING, scale=(1.6, 0.05, 0.5))
    smooth_sphere(f"df_{dk}_wdL", r=0.16, segs=12, rings=6, loc=(-0.04, 0, 0.20), parent=wing_L_e, mat=MAT_DRAGONFLY_WING, scale=(1.4, 0.05, 0.5))
    smooth_sphere(f"df_{dk}_wuR", r=0.18, segs=12, rings=6, loc=(0.04, 0, -0.20), parent=wing_R_e, mat=MAT_DRAGONFLY_WING, scale=(1.6, 0.05, 0.5))
    smooth_sphere(f"df_{dk}_wdR", r=0.16, segs=12, rings=6, loc=(-0.04, 0, -0.20), parent=wing_R_e, mat=MAT_DRAGONFLY_WING, scale=(1.4, 0.05, 0.5))
    dragonflies.append({"p": dp, "wL": wing_L_e, "wR": wing_R_e, "phase": dk * 1.0,
                        "base": (dp.location.x, dp.location.y, dp.location.z)})


# --- 60 pollen particles --------------------------------------------------
pollen = []
for pk in range(60):
    pmat = MAT_POLLEN_A if pk % 2 == 0 else MAT_POLLEN_B
    px = random.uniform(-8, 8)
    py = random.uniform(1.5, 6)
    pz = random.uniform(-1.5, 5)
    p_obj = smooth_sphere(f"pollen_{pk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(px, py, pz), mat=pmat)
    p_obj["_base"] = (px, py, pz)
    p_obj["_phase"] = pk * 0.18
    p_obj["_drift"] = random.uniform(0.4, 1.2)
    pollen.append(p_obj)


# --- ANIMATIONS ----------------------------------------------------------
DURATION = 6.0
FRAMES = scene.frame_end
DT = DURATION / FRAMES


def kf(obj, frame, attr, val):
    if attr == "location":
        obj.location = val
        obj.keyframe_insert(data_path="location", frame=frame)
    elif attr == "rotation_euler":
        obj.rotation_euler = val
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    elif attr == "scale":
        obj.scale = val
        obj.keyframe_insert(data_path="scale", frame=frame)


for f in range(1, FRAMES + 1):
    t = (f - 1) * DT
    tt = t / DURATION

    # --- 8 butterflies orbit 3D + flap
    for bd in butterflies:
        ang = bd["phase"] + tt * 2 * math.pi * bd["spd"]
        bx = math.cos(ang) * bd["orbit_r"]
        bz = math.sin(ang) * bd["orbit_r"]
        by = bd["orbit_y"] + 0.6 * math.sin(2 * math.pi * tt * 1.5 + bd["phase"])
        kf(bd["p"], f, "location", (bx, by, bz))
        face_yaw = ang + math.pi / 2 * (1 if bd["spd"] > 0 else -1)
        roll = math.radians(15 * math.sin(2 * math.pi * tt * 2.5 + bd["phase"]))
        kf(bd["p"], f, "rotation_euler", (roll, face_yaw, 0))
        # wings flap synchronized L/R
        flap = math.radians(70) * math.sin(2 * math.pi * tt * 8 + bd["phase"])
        kf(bd["wL"], f, "rotation_euler", (flap, 0, 0))
        kf(bd["wR"], f, "rotation_euler", (-flap, 0, 0))

    # --- 20 flowers : pulse scale gentle
    for fi, fp in enumerate(flowers):
        ph = fp["_phase"]
        ps = 1.0 + 0.06 * math.sin(2 * math.pi * tt * 1.8 + ph * math.pi)
        kf(fp, f, "scale", (ps, ps, ps))

    # --- 6 bees orbit short around flowers + super-fast flap
    for bd in bees:
        tx, ty, tz = bd["tx"], bd["ty"], bd["tz"]
        ang = bd["phase"] + tt * 2 * math.pi * 1.5
        # tight orbit radius
        bx = tx + math.cos(ang) * 0.35
        bz = tz + math.sin(ang) * 0.35
        by = ty + 0.15 * math.sin(2 * math.pi * tt * 2.0 + bd["phase"])
        kf(bd["p"], f, "location", (bx, by, bz))
        kf(bd["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        # 4 wings super fast flap
        wflap = math.radians(40) * math.sin(2 * math.pi * tt * 20 + bd["phase"])
        kf(bd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(bd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # --- 4 dragonflies darting (saccade movements)
    for dd in dragonflies:
        bxs, bys, bzs = dd["base"]
        ph = dd["phase"]
        # saccade : combine slow drift + fast jumps
        slow_ang = ph + tt * 2 * math.pi * 0.5
        dx = bxs + math.cos(slow_ang) * 2.5 + 0.5 * math.sin(2 * math.pi * tt * 4 + ph)
        dz = bzs + math.sin(slow_ang) * 2.5 + 0.5 * math.cos(2 * math.pi * tt * 4 + ph)
        dy = bys + 0.8 * math.sin(2 * math.pi * tt * 1.8 + ph)
        kf(dd["p"], f, "location", (dx, dy, dz))
        kf(dd["p"], f, "rotation_euler", (math.radians(10 * math.sin(2 * math.pi * tt * 3 + ph)), slow_ang + math.pi / 2, 0))
        wflap = math.radians(35) * math.sin(2 * math.pi * tt * 18 + ph)
        kf(dd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(dd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # --- 15 grass blades sway
    for gi, gp in enumerate(grass_blades):
        bx = math.radians(15) * math.sin(2 * math.pi * tt * 2 + gi * 0.5)
        bz = math.radians(10) * math.cos(2 * math.pi * tt * 2.2 + gi * 0.3)
        kf(gp, f, "rotation_euler", (bx, 0, bz))

    # --- fountain jets rise + scale
    for ji, jp in enumerate(jets):
        ph = jp["_phase"]
        local = (tt * 1.8 + ph) % 1.0
        sc_y = 1.0 + local * 1.5
        kf(jp, f, "scale", (1.0, sc_y, 1.0))

    # --- 60 pollen drift 3D + scintille
    for plk in pollen:
        bxp, byp, bzp = plk["_base"]
        ph = plk["_phase"]
        drift = plk["_drift"]
        nx = bxp + 1.0 * math.sin(2 * math.pi * tt * 0.8 * drift + ph * math.pi)
        ny = byp + 0.5 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi)
        nz = bzp + 0.7 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi * 0.8)
        kf(plk, f, "location", (nx, ny, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 3.0 + ph * math.pi))
        kf(plk, f, "scale", (sc, sc, sc))

    # --- 4 clouds drift
    for cp in clouds:
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 5 - 2.5
        if new_x > 14:
            new_x -= 28
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))

    # --- sun pulse + halos breathe
    sp = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sp, sp, sp))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2, sun_halo_3]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_butterfly_garden] wrote {OUT}")
