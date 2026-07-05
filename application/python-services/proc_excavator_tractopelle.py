"""
proc_excavator_tractopelle.py — 139e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — exemple littéral cité par l'utilisateur ("tractopelle").

Tractopelle/excavator avec bras articulé :
- caisse principale jaune bevelée + smooth
- cabine vitrée tilted avec windshield translucent
- 2 chenilles complètes (12 track plates + 2 wheels alloy chacune)
- bras articulé : 3 segments hydrauliques avec pistons
- godet à pince à 5 dents
- 2 phares LED + halos
- escalier accès (3 marches)
- 2 miroirs réfléchissants
- drapeau warning orange émissif flottant
- échappement avec fumée
- sol terre + pavé damier
- tas de gravats (10 rocks)
- 3 cones travaux émissifs
- ciel matin clair

Animations multi-axes simultanées :
- bras 3 segments : se déplie + se replie cycliquement (rotation X par segment)
- godet : ouverture/fermeture (rotation Z) + scoop motion
- 2 chenilles : tracks translation + 4 wheels rotation X
- cabine : pivote Y ±25° (turret rotation)
- drapeau : flotte (segments wave)
- 2 phares LED : pulse intense
- 3 cones travaux : strobe alternance
- échappement : 6 puffs smoke rise
- vehicle bob + tilt subtle

Sortie : output/3d/pbr_excavator_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_excavator_proc.glb"))

random.seed(0xC0FFEE)

# --- helpers ----------------------------------------------------------------

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


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(size_xyz[0], size_xyz[1], size_xyz[2]), verts=bm.verts)
    bmesh.ops.bevel(
        bm,
        geom=bm.edges[:] + bm.verts[:],
        offset=bevel_offset,
        segments=bevel_segments,
        profile=0.5,
        affect='EDGES',
    )
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    if smooth:
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
MAT_SKY = make_mat("sky", (0.65, 0.78, 0.92), roughness=1.0,
                    emi=(0.45, 0.62, 0.85), emi_strength=0.5)
MAT_CLOUD = make_mat("cloud", (0.95, 0.97, 1.0), roughness=1.0, alpha=0.9,
                      emi=(0.85, 0.90, 0.95), emi_strength=0.3)
MAT_GROUND_DIRT = make_mat("ground_dirt", (0.45, 0.30, 0.18), roughness=0.95)
MAT_GROUND_GRAVEL = make_mat("ground_gravel", (0.35, 0.32, 0.28), roughness=0.95)
MAT_PAVEMENT = make_mat("pavement", (0.55, 0.52, 0.50), roughness=0.85,
                          emi=(0.15, 0.15, 0.15), emi_strength=0.2)
MAT_YELLOW = make_mat("yellow", (1.0, 0.78, 0.05), metallic=0.55, roughness=0.30,
                        emi=(0.40, 0.30, 0.02), emi_strength=0.35)
MAT_YELLOW_DARK = make_mat("yellow_dark", (0.70, 0.50, 0.05), metallic=0.55, roughness=0.40,
                             emi=(0.25, 0.18, 0.02), emi_strength=0.30)
MAT_BLACK_RUBBER = make_mat("rubber", (0.05, 0.05, 0.05), roughness=0.85)
MAT_BLACK_METAL = make_mat("black_metal", (0.10, 0.10, 0.12), metallic=0.80, roughness=0.30)
MAT_STEEL = make_mat("steel", (0.55, 0.55, 0.60), metallic=0.90, roughness=0.25,
                       emi=(0.10, 0.10, 0.12), emi_strength=0.25)
MAT_PISTON = make_mat("piston", (0.85, 0.85, 0.92), metallic=0.95, roughness=0.10,
                        emi=(0.20, 0.20, 0.22), emi_strength=0.25)
MAT_CABIN_GLASS = make_mat("cabin_glass", (0.15, 0.25, 0.35), roughness=0.0, alpha=0.50, metallic=0.55,
                             emi=(0.10, 0.18, 0.30), emi_strength=0.45)
MAT_HYDRAULIC = make_mat("hydraulic", (0.30, 0.30, 0.30), metallic=0.80, roughness=0.25,
                           emi=(0.08, 0.08, 0.10), emi_strength=0.20)
MAT_HEADLIGHT = make_mat("headlight", (1.0, 0.95, 0.85), roughness=0.0,
                           emi=(1.0, 0.95, 0.85), emi_strength=14.0)
MAT_HL_HALO = make_mat("hl_halo", (1.0, 0.92, 0.80), roughness=0.0, alpha=0.30,
                         emi=(1.0, 0.92, 0.80), emi_strength=4.5)
MAT_WARNING_FLAG = make_mat("warning_flag", (1.0, 0.45, 0.05), roughness=0.50,
                              emi=(0.55, 0.20, 0.02), emi_strength=0.50)
MAT_WARNING_STRIPE_BLACK = make_mat("warning_stripe", (0.05, 0.05, 0.05), roughness=0.50)
MAT_CONE = make_mat("cone", (1.0, 0.30, 0.10), roughness=0.40,
                      emi=(0.65, 0.15, 0.05), emi_strength=4.0)
MAT_CONE_STRIPE = make_mat("cone_stripe", (0.95, 0.95, 0.95), roughness=0.40,
                             emi=(0.40, 0.40, 0.42), emi_strength=0.4)
MAT_SMOKE = make_mat("smoke", (0.55, 0.55, 0.55), roughness=1.0, alpha=0.65,
                       emi=(0.35, 0.35, 0.35), emi_strength=0.4)
MAT_ROCK = make_mat("rock", (0.40, 0.35, 0.28), roughness=0.95)
MAT_MIRROR = make_mat("mirror", (0.95, 0.95, 0.98), metallic=0.99, roughness=0.02,
                        emi=(0.30, 0.30, 0.35), emi_strength=0.3)

# --- backdrop : morning sky ----------------------------------------------
sky = cube_used = beveled_cube("sky_back", (40, 0.2, 14), bevel_offset=0.05, bevel_segments=2, loc=(0, 8, 8), mat=MAT_SKY)
# 4 clouds
for i in range(4):
    cx = -10 + i * 6
    cz = 9
    cy = 13
    cl = smooth_sphere(f"cloud_{i}", r=1.4, segs=18, rings=12, loc=(cx, cy, cz), mat=MAT_CLOUD, scale=(1.5, 0.5, 1.0))

# --- ground (dirt + gravel mix) -------------------------------------------
ground = beveled_cube("ground", (30, 0.1, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND_DIRT)
# pavement section (driveway)
pavement = beveled_cube("pavement", (12, 0.05, 5), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.01, 5), mat=MAT_PAVEMENT)
# gravel area
gravel = beveled_cube("gravel", (8, 0.04, 5), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.01, -5), mat=MAT_GROUND_GRAVEL)

# --- 10 rocks (gravats) ---------------------------------------------
for i in range(10):
    rx = random.uniform(-3, 3) + 7
    rz = random.uniform(-2, 2) - 4
    h = random.uniform(0.20, 0.50)
    r = smooth_sphere(f"rock_{i}", r=h, segs=16, rings=10, loc=(rx, h * 0.6, rz), mat=MAT_ROCK, scale=(1.3, 0.7, 1.0))

# --- 3 cones travaux émissifs --------------------------------------
for i, (cx, cz) in enumerate([(-4, 4), (4, 4), (0, 5.5)]):
    cp = empty(f"cone_{i}", (cx, 0, cz))
    # base
    base = smooth_cone(f"cone_{i}_base", r1=0.30, r2=0.30, depth=0.05, segs=20, loc=(0, 0.025, 0), parent=cp, mat=MAT_CONE)
    base.rotation_euler = (math.radians(90), 0, 0)
    # main cone (orange)
    main = smooth_cone(f"cone_{i}_main", r1=0.20, r2=0.04, depth=0.55, segs=20, loc=(0, 0.30, 0), parent=cp, mat=MAT_CONE)
    main.rotation_euler = (math.radians(90), 0, 0)
    # white reflective stripe
    stripe = smooth_cone(f"cone_{i}_stripe", r1=0.16, r2=0.10, depth=0.08, segs=20, loc=(0, 0.30, 0), parent=cp, mat=MAT_CONE_STRIPE)
    stripe.rotation_euler = (math.radians(90), 0, 0)

# --- excavator main body --------------------------------------------
excavator = empty("excavator", (-2.0, 0, 0))

# --- chenilles (2 tracks) ---------------------------------------------
def make_track(name, x_local, parent):
    p = empty(name, (x_local, 0.40, 0), parent=parent)
    # base track plate (long bevelled cube)
    base = beveled_cube(f"{name}_base", (2.4, 0.30, 0.50), bevel_offset=0.10, bevel_segments=3, loc=(0, 0, 0), parent=p, mat=MAT_BLACK_RUBBER)
    # 12 track plates on top (visible treads)
    for k in range(12):
        kx = -1.10 + k * 0.20
        plate = beveled_cube(f"{name}_plate_{k}", (0.16, 0.06, 0.52), bevel_offset=0.03, bevel_segments=2, loc=(kx, 0.18, 0), parent=p, mat=MAT_BLACK_METAL)
    # 2 large wheels (one each end)
    for side, dx in [("F", 1.05), ("B", -1.05)]:
        w = smooth_cone(f"{name}_w_{side}", r1=0.32, r2=0.32, depth=0.45, segs=24, loc=(dx, -0.05, 0), parent=p, mat=MAT_STEEL)
        w.rotation_euler = (0, math.radians(90), 0)
        # alloy hub
        hub = smooth_cone(f"{name}_w_{side}_hub", r1=0.18, r2=0.18, depth=0.46, segs=20, loc=(dx, -0.05, 0), parent=p, mat=MAT_YELLOW_DARK)
        hub.rotation_euler = (0, math.radians(90), 0)
        # 4 spokes
        for k in range(4):
            ka = k * (math.pi / 2)
            spoke = beveled_cube(f"{name}_w_{side}_s_{k}", (0.04, 0.04, 0.47), bevel_offset=0.01, bevel_segments=2, loc=(dx, -0.05, 0), parent=p, mat=MAT_YELLOW_DARK)
            spoke.rotation_euler = (ka, 0, 0)
    # 3 middle support wheels (smaller)
    for k, kx in enumerate([-0.5, 0, 0.5]):
        sw = smooth_cone(f"{name}_sw_{k}", r1=0.20, r2=0.20, depth=0.40, segs=20, loc=(kx, -0.10, 0), parent=p, mat=MAT_BLACK_METAL)
        sw.rotation_euler = (0, math.radians(90), 0)
    return p

track_L = make_track("track_L", 0, excavator)
track_L.location = (0, 0.40, 0.85)
track_R = make_track("track_R", 0, excavator)
track_R.location = (0, 0.40, -0.85)

# --- chassis principal ---------------------------------------------
chassis_base = beveled_cube("chassis_base", (2.8, 0.30, 2.0), bevel_offset=0.12, bevel_segments=4, loc=(0, 0.85, 0), parent=excavator, mat=MAT_YELLOW)

# --- turret (rotating part) ----------------------------------------
turret_p = empty("turret_p", (0, 1.0, 0), parent=excavator)
turret_base = smooth_cone("turret_base", r1=1.0, r2=0.95, depth=0.30, segs=24, loc=(0, 0.15, 0), parent=turret_p, mat=MAT_YELLOW_DARK)
turret_base.rotation_euler = (math.radians(90), 0, 0)

# --- body (sur turret) ---------------------------------------------
body_main = beveled_cube("body_main", (1.8, 0.85, 1.5), bevel_offset=0.15, bevel_segments=4, loc=(-0.20, 0.75, 0), parent=turret_p, mat=MAT_YELLOW)
# warning stripes (black on yellow)
for k in range(3):
    kz = -0.6 + k * 0.6
    stripe = beveled_cube(f"warn_stripe_{k}", (1.85, 0.10, 0.08), bevel_offset=0.02, bevel_segments=2, loc=(-0.20, 0.40, kz), parent=turret_p, mat=MAT_WARNING_STRIPE_BLACK)

# --- cabine vitrée ---------------------------------------------------
cabin_p = empty("cabin_p", (0.7, 1.50, 0), parent=turret_p)
# cabin frame
cabin_frame = beveled_cube("cabin_frame", (1.0, 1.0, 1.2), bevel_offset=0.10, bevel_segments=4, loc=(0, 0, 0), parent=cabin_p, mat=MAT_YELLOW)
# windshield (slanted forward)
windshield = beveled_cube("cabin_windshield", (0.1, 0.85, 1.05), bevel_offset=0.05, bevel_segments=3, loc=(0.52, 0.05, 0), parent=cabin_p, mat=MAT_CABIN_GLASS)
windshield.rotation_euler = (0, 0, math.radians(-12))
# rear window
rear_win = beveled_cube("cabin_rear", (0.1, 0.7, 1.05), bevel_offset=0.05, bevel_segments=3, loc=(-0.52, 0.05, 0), parent=cabin_p, mat=MAT_CABIN_GLASS)
rear_win.rotation_euler = (0, 0, math.radians(12))
# 2 side windows
for side, dz in [("L", 0.55), ("R", -0.55)]:
    sw = beveled_cube(f"cabin_side_{side}", (0.85, 0.75, 0.05), bevel_offset=0.05, bevel_segments=3, loc=(0, 0.05, dz), parent=cabin_p, mat=MAT_CABIN_GLASS)
# cabin roof
roof = beveled_cube("cabin_roof", (1.05, 0.08, 1.25), bevel_offset=0.05, bevel_segments=3, loc=(0, 0.55, 0), parent=cabin_p, mat=MAT_YELLOW_DARK)

# --- 2 phares LED sur cabine ---------------------------------------
headlights = []
for side, dz in [("L", 0.45), ("R", -0.45)]:
    hl_p = empty(f"hl_p_{side}", (0.55, 0.40, dz), parent=cabin_p)
    hl = smooth_sphere(f"hl_{side}", r=0.10, segs=18, rings=14, loc=(0, 0, 0), parent=hl_p, mat=MAT_HEADLIGHT)
    hl.scale = (0.4, 1.0, 1.0)
    halo = smooth_sphere(f"hl_halo_{side}", r=0.22, segs=16, rings=12, loc=(0.04, 0, 0), parent=hl_p, mat=MAT_HL_HALO)
    halo.scale = (0.3, 1.0, 1.0)
    headlights.append(hl)

# --- 2 miroirs sur cabine ---------------------------------------------
for side, dz in [("L", 0.62), ("R", -0.62)]:
    mr_p = empty(f"mirror_p_{side}", (0.50, 0.30, dz), parent=cabin_p)
    arm = smooth_cone(f"mirror_arm_{side}", r1=0.02, r2=0.02, depth=0.20, segs=10, loc=(0, 0, 0), parent=mr_p, mat=MAT_STEEL)
    arm.rotation_euler = (0, 0, math.radians(90))
    glass = beveled_cube(f"mirror_glass_{side}", (0.05, 0.18, 0.18), bevel_offset=0.02, bevel_segments=3, loc=(0, 0, 0.18 if side == "L" else -0.18), parent=mr_p, mat=MAT_MIRROR)

# --- arm articulé : 3 segments hydrauliques ---------------------------
# Boom (1st segment, attached to turret, swings up/down)
boom_p = empty("boom_p", (0.50, 1.20, 0), parent=turret_p)
boom = beveled_cube("boom", (2.2, 0.30, 0.40), bevel_offset=0.10, bevel_segments=3, loc=(1.05, 0, 0), parent=boom_p, mat=MAT_YELLOW)
# hydraulic cylinder for boom (parallel to boom, smaller)
boom_hyd = smooth_cone("boom_hyd", r1=0.10, r2=0.10, depth=1.8, segs=18, loc=(0.85, -0.25, 0), parent=boom_p, mat=MAT_HYDRAULIC)
boom_hyd.rotation_euler = (0, 0, math.radians(90))
# piston rod inside (chrome smaller)
boom_piston = smooth_cone("boom_piston", r1=0.05, r2=0.05, depth=1.5, segs=14, loc=(1.4, -0.25, 0), parent=boom_p, mat=MAT_PISTON)
boom_piston.rotation_euler = (0, 0, math.radians(90))

# Stick (2nd segment, attached to end of boom)
stick_p = empty("stick_p", (2.10, 0, 0), parent=boom_p)
stick = beveled_cube("stick", (1.6, 0.25, 0.35), bevel_offset=0.10, bevel_segments=3, loc=(0.80, 0, 0), parent=stick_p, mat=MAT_YELLOW)
# hydraulic for stick
stick_hyd = smooth_cone("stick_hyd", r1=0.08, r2=0.08, depth=1.2, segs=16, loc=(0.50, 0.30, 0), parent=stick_p, mat=MAT_HYDRAULIC)
stick_hyd.rotation_euler = (0, 0, math.radians(90))
stick_piston = smooth_cone("stick_piston", r1=0.04, r2=0.04, depth=0.9, segs=14, loc=(0.85, 0.30, 0), parent=stick_p, mat=MAT_PISTON)
stick_piston.rotation_euler = (0, 0, math.radians(90))

# Bucket (3rd segment, attached to end of stick)
bucket_p = empty("bucket_p", (1.60, 0, 0), parent=stick_p)
# bucket body (curved bottom via beveled cube + rotated)
bucket_body = beveled_cube("bucket_body", (0.6, 0.5, 0.7), bevel_offset=0.15, bevel_segments=4, loc=(0.25, -0.20, 0), parent=bucket_p, mat=MAT_YELLOW)
# 5 dents (teeth) at front of bucket
for k in range(5):
    kz = -0.30 + k * 0.15
    tooth = smooth_cone(f"bucket_tooth_{k}", r1=0.05, r2=0.01, depth=0.18, segs=8, loc=(0.55, -0.30, kz), parent=bucket_p, mat=MAT_STEEL)
    tooth.rotation_euler = (0, 0, math.radians(90))
# bucket hydraulic
bucket_hyd = smooth_cone("bucket_hyd", r1=0.06, r2=0.06, depth=0.60, segs=14, loc=(0.0, 0.20, 0), parent=bucket_p, mat=MAT_HYDRAULIC)
bucket_hyd.rotation_euler = (0, 0, math.radians(90))
bucket_piston = smooth_cone("bucket_piston", r1=0.03, r2=0.03, depth=0.50, segs=12, loc=(0.30, 0.20, 0), parent=bucket_p, mat=MAT_PISTON)
bucket_piston.rotation_euler = (0, 0, math.radians(90))

# --- échappement avec smoke -------------------------------------------
exhaust_p = empty("exhaust_p", (-0.80, 1.55, 0.50), parent=turret_p)
exhaust_pipe = smooth_cone("exhaust_pipe", r1=0.08, r2=0.08, depth=0.6, segs=14, loc=(0, 0.3, 0), parent=exhaust_p, mat=MAT_STEEL)
exhaust_pipe.rotation_euler = (math.radians(90), 0, 0)
# 6 smoke puffs
exhaust_smokes = []
for k in range(6):
    py = 0.7 + k * 0.4
    pr = 0.10 + k * 0.04
    puff = smooth_sphere(f"exhaust_smoke_{k}", r=pr, segs=14, rings=10, loc=(0, py, 0), parent=exhaust_p, mat=MAT_SMOKE)
    exhaust_smokes.append((puff, k))

# --- drapeau warning orange ----------------------------------------
flag_p = empty("flag_p", (-0.95, 1.85, 0), parent=turret_p)
flag_pole = smooth_cone("flag_pole", r1=0.025, r2=0.020, depth=0.6, segs=10, loc=(0, 0.3, 0), parent=flag_p, mat=MAT_STEEL)
flag_pole.rotation_euler = (math.radians(90), 0, 0)
# 5 flag segments (wave-animated)
flag_segs = []
for k in range(5):
    seg = beveled_cube(f"flag_seg_{k}", (0.06, 0.25, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(0.04 + k * 0.06, 0.50, 0), parent=flag_p, mat=MAT_WARNING_FLAG)
    flag_segs.append(seg)

# --- escalier accès cabine -------------------------------------------
stairs_p = empty("stairs", (0.5, 0.30, 1.05), parent=excavator)
for k in range(3):
    step = beveled_cube(f"stair_{k}", (0.35, 0.05, 0.30), bevel_offset=0.02, bevel_segments=2, loc=(0, k * 0.20, k * -0.15), parent=stairs_p, mat=MAT_YELLOW_DARK)
# 2 handrails
for side, dz in [("L", 0.18), ("R", -0.18)]:
    rail = smooth_cone(f"stair_rail_{side}", r1=0.03, r2=0.03, depth=0.7, segs=8, loc=(0, 0.40, dz), parent=stairs_p, mat=MAT_STEEL)
    rail.rotation_euler = (math.radians(45), 0, 0)

# --- animation --------------------------------------------------------------

def kf_loc(o, f, l):
    o.location = l
    o.keyframe_insert(data_path="location", frame=f)


def kf_scale(o, f, s):
    o.scale = s
    o.keyframe_insert(data_path="scale", frame=f)


def kf_rot(o, f, r):
    o.rotation_euler = r
    o.keyframe_insert(data_path="rotation_euler", frame=f)


FRAMES = 180

# 2 chenilles : 4 large wheels rotate (left + right)
for track in [track_L, track_R]:
    for child in track.children:
        if "_w_F" in child.name or "_w_B" in child.name or "_sw_" in child.name:
            for f in range(1, FRAMES + 1, 2):
                tt = (f - 1) / (FRAMES - 1)
                # wheels rotate as if vehicle moves
                kf_rot(child, f, (tt * math.pi * 8, math.radians(90), 0))

# vehicle subtle bob + tilt
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    by = 0 + 0.03 * math.sin(tt * math.pi * 4.0)
    tilt = math.radians(2) * math.sin(tt * math.pi * 3.0)
    kf_loc(excavator, f, (-2.0, by, 0))
    kf_rot(excavator, f, (tilt, 0, 0))

# turret rotates ±25° around Y axis
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = math.radians(25) * math.sin(tt * math.pi * 2.0)
    kf_rot(turret_p, f, (0, angle, 0))

# boom : swings up/down ±20°
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    # working motion : down→up→down
    angle = math.radians(-15) + math.radians(35) * (math.sin(tt * math.pi * 2.0) + 1) * 0.5
    kf_rot(boom_p, f, (0, 0, angle))

# stick : also articulates (more dramatic)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    # phased differently from boom for compound motion
    angle = math.radians(-25) + math.radians(50) * (math.cos(tt * math.pi * 2.0 + 0.5) + 1) * 0.5
    kf_rot(stick_p, f, (0, 0, angle))

# bucket : opens and closes scoop
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    # cyclical scoop : 0→closed→open→0
    angle = math.radians(-60) * (math.sin(tt * math.pi * 4.0) + 1) * 0.5
    kf_rot(bucket_p, f, (0, 0, angle))

# 2 headlights pulse
for hl in headlights:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 6.0)
        kf_scale(hl, f, (0.4 * s, 1.0 * s, 1.0 * s))

# 3 cones strobe (alternance)
for i in range(3):
    cone_main = bpy.data.objects.get(f"cone_{i}_main")
    if cone_main:
        for f in range(1, FRAMES + 1, 3):
            tt = (f - 1) / (FRAMES - 1)
            phase = i * (math.pi * 2 / 3)
            on = math.sin(tt * math.pi * 6.0 + phase) > 0
            s = 1.05 if on else 0.95
            kf_scale(cone_main, f, (s, s, s))

# 6 exhaust smoke puffs rise
for puff, k in exhaust_smokes:
    phase = k * 8
    base_y = 0.7 + k * 0.4
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 60
        lt = local_f / 60
        dy = base_y + lt * 1.5
        dx = math.sin(lt * math.pi * 3.0) * 0.20
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# flag waves (5 segments offset)
for i, seg in enumerate(flag_segs):
    base_x = seg.location.x
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.sin(i * 0.5 + tt * math.pi * 7.0)
        kz = wave * 0.10
        ky = 0.50 + math.cos(i * 0.5 + tt * math.pi * 7.0) * 0.04
        kf_loc(seg, f, (base_x, ky, kz))
        kf_rot(seg, f, (0, 0, wave * 0.20))

# --- export -----------------------------------------------------------------

# I used cube_used variable as alias; remove placeholder if exists
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_excavator] wrote {OUT}")
