"""
proc_dragon_flying.py — 145e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Dragon fantasy en vol smooth shaded :
- corps reptilien profilé bevelé (sphère étirée + neck multi-segments)
- tête énorme avec 2 cornes + 2 yeux émissifs verts + mâchoire
- 2 grandes ailes membraneuses (3 segments hiérarchiques chacune, anim flap synchrone)
- 4 pattes griffues avec doigts
- queue 8 segments propagated wave swish
- 30 écailles dorsales spikes
- flammes émissives crachées par gueule (8 segments)
- ciel coucher dramatique
- 4 nuages
- montagnes background
- arbres morts

Animations multi-axes simultanées :
- 2 ailes : flap synchronized rotation X ±35° (chaque segment hierarchical)
- queue 8 segs : swish propagated wave
- body bob + slight rotate
- tête tourne + jaw ouvre
- flammes pulse intense + emerge from mouth animated
- eyes pulse vert
- dragon flying path : translate XY circle + rotate banking

Sortie : output/3d/pbr_dragon_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_dragon_proc.glb"))

random.seed(0xCAFE0E)

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


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
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
    if smooth:
        smooth_shade(me)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY_TOP = make_mat("sky_top", (0.55, 0.20, 0.30), roughness=1.0,
                         emi=(0.50, 0.18, 0.28), emi_strength=0.5)
MAT_SKY_LOW = make_mat("sky_low", (1.0, 0.55, 0.20), roughness=1.0,
                         emi=(0.85, 0.45, 0.15), emi_strength=0.6)
MAT_CLOUD = make_mat("cloud", (0.85, 0.55, 0.45), roughness=1.0, alpha=0.85,
                       emi=(0.65, 0.40, 0.30), emi_strength=0.3)
MAT_DRAGON_BODY = make_mat("dragon_body", (0.45, 0.15, 0.08), roughness=0.45, metallic=0.40,
                             emi=(0.20, 0.05, 0.03), emi_strength=0.20)
MAT_DRAGON_BELLY = make_mat("dragon_belly", (0.65, 0.40, 0.15), roughness=0.45,
                              emi=(0.25, 0.15, 0.05), emi_strength=0.20)
MAT_DRAGON_DARK = make_mat("dragon_dark", (0.15, 0.05, 0.03), roughness=0.6)
MAT_DRAGON_HORN = make_mat("horn", (0.10, 0.05, 0.03), roughness=0.5)
MAT_WING_MEMBRANE = make_mat("wing_membrane", (0.55, 0.15, 0.10), roughness=0.4, alpha=0.85,
                               emi=(0.30, 0.08, 0.05), emi_strength=0.25)
MAT_WING_BONE = make_mat("wing_bone", (0.25, 0.08, 0.05), roughness=0.7)
MAT_CLAW = make_mat("claw", (0.05, 0.03, 0.02), roughness=0.4)
MAT_TEETH = make_mat("teeth", (0.92, 0.90, 0.85), roughness=0.4,
                       emi=(0.40, 0.40, 0.35), emi_strength=0.3)
MAT_EYE = make_mat("eye", (0.20, 1.0, 0.30), roughness=0.0,
                     emi=(0.20, 1.0, 0.30), emi_strength=10.0)
MAT_FIRE_CORE = make_mat("fire_core", (1.0, 0.92, 0.30), roughness=0.0,
                           emi=(1.0, 0.92, 0.30), emi_strength=16.0)
MAT_FIRE = make_mat("fire", (1.0, 0.45, 0.10), roughness=0.0, alpha=0.85,
                      emi=(1.0, 0.45, 0.10), emi_strength=12.0)
MAT_FIRE_TIP = make_mat("fire_tip", (0.55, 0.20, 0.10), roughness=0.0, alpha=0.65,
                          emi=(0.55, 0.20, 0.10), emi_strength=6.0)
MAT_MOUNTAIN = make_mat("mountain", (0.25, 0.18, 0.20), roughness=0.95)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.20, 0.12, 0.08), roughness=0.95)
MAT_SCALE = make_mat("scale", (0.30, 0.08, 0.05), metallic=0.5, roughness=0.4,
                       emi=(0.15, 0.03, 0.02), emi_strength=0.2)
MAT_GROUND = make_mat("ground", (0.20, 0.10, 0.08), roughness=0.95)

# --- backdrop : dramatic sunset sky ----------------------------------
sky_top = beveled_cube("sky_top", (40, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 12), mat=MAT_SKY_TOP)
sky_low = beveled_cube("sky_low", (40, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 4), mat=MAT_SKY_LOW)

# 4 clouds
for i, (cx, cy, cz) in enumerate([(-10, 13, 6), (-3, 14, 4), (5, 13, 5), (11, 14, 7)]):
    cl = smooth_sphere(f"cloud_{i}", r=random.uniform(1.4, 2.0), segs=20, rings=14, loc=(cx, cy, cz), mat=MAT_CLOUD, scale=(1.7, 0.55, 1.1))

# 3 background mountains
for i, (mx, mh, mw) in enumerate([(-8, 5, 6), (8, 6, 5), (0, 4, 4)]):
    mp = empty(f"mount_{i}", (mx, 0, 9))
    m = smooth_cone(f"mount_{i}_body", r1=mw, r2=0.4, depth=mh, segs=14, loc=(0, mh / 2, 0), parent=mp, mat=MAT_MOUNTAIN)
    m.rotation_euler = (math.radians(90), 0, 0)

# 4 dead trees
for i, (tx, tz) in enumerate([(-10, 4), (10, 4), (-6, 6), (6, 6)]):
    tp = empty(f"tree_{i}", (tx, 0, tz))
    trunk = smooth_cone(f"tree_{i}_trunk", r1=0.20, r2=0.10, depth=2.5, segs=10, loc=(0, 1.25, 0), parent=tp, mat=MAT_TREE_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, math.radians(random.uniform(-5, 5)))
    # 4 bare branches
    for j in range(4):
        ja = j * (math.pi / 2)
        branch = smooth_cone(f"tree_{i}_b_{j}", r1=0.06, r2=0.02, depth=1.0, segs=6, loc=(0, 2.2, 0), parent=tp, mat=MAT_TREE_TRUNK)
        branch.rotation_euler = (math.radians(60), 0, ja)

# ground
ground = beveled_cube("ground", (30, 0.1, 18), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND)

# --- dragon ------------------------------------------------------------
dragon = empty("dragon", (0, 6, 0))

# main body (sphère étirée smooth)
def make_body(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.7)
    bmesh.ops.scale(bm, vec=(2.5, 1.0, 1.1), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0, 0)
    me.materials.append(MAT_DRAGON_BODY)
    smooth_shade(me)
    return o

body = make_body("dragon_body_main", dragon)

# belly underside
belly = smooth_sphere("dragon_belly", r=0.6, segs=24, rings=18, loc=(0, -0.30, 0), parent=dragon, mat=MAT_DRAGON_BELLY, scale=(2.7, 0.4, 1.05))

# 30 dorsal scales/spikes
for k in range(30):
    kx = -2.0 + (k / 29) * 4.0
    if k < 20:
        # main body spikes
        sx = kx
        sy = 0.50 + 0.10 * math.sin(k * 0.5)
    else:
        # tail tip area
        sx = -2.0 - (k - 20) * 0.5
        sy = 0.20
    spike = smooth_cone(f"scale_{k}", r1=0.08, r2=0.0, depth=0.20, segs=6, loc=(sx, sy, 0), parent=dragon, mat=MAT_SCALE)
    spike.rotation_euler = (math.radians(-90), 0, 0)

# neck (3 segments curving up)
neck_p = empty("neck_p", (1.85, 0.20, 0), parent=dragon)
neck_p.rotation_euler = (0, 0, math.radians(-35))
for j in range(3):
    h = 0.20 + j * 0.30
    rj = 0.45 - j * 0.08
    seg = smooth_cone(f"neck_seg_{j}", r1=rj, r2=rj * 0.85, depth=0.40, segs=18, loc=(0, h, 0), parent=neck_p, mat=MAT_DRAGON_BODY)
    seg.rotation_euler = (math.radians(90), 0, 0)

# head
head_p = empty("head_p", (1.95, 1.45, 0), parent=dragon)
head_p.rotation_euler = (0, 0, math.radians(-15))
# main skull
upper_head = smooth_sphere("upper_head", r=0.50, segs=24, rings=18, loc=(0.30, 0.10, 0), parent=head_p, mat=MAT_DRAGON_BODY, scale=(1.7, 1.0, 1.0))
# snout
snout = smooth_cone("snout", r1=0.38, r2=0.20, depth=0.55, segs=18, loc=(0.80, 0.05, 0), parent=head_p, mat=MAT_DRAGON_BODY)
snout.rotation_euler = (0, math.radians(90), 0)
# 2 cornes recourbées
for side, dz in [("L", 0.30), ("R", -0.30)]:
    # base of horn
    horn_base = smooth_cone(f"horn_base_{side}", r1=0.12, r2=0.05, depth=0.65, segs=12, loc=(0.0, 0.40, dz), parent=head_p, mat=MAT_DRAGON_HORN)
    horn_base.rotation_euler = (math.radians(-120), 0, 0)
    # curved tip (smaller, angled back)
    horn_tip = smooth_cone(f"horn_tip_{side}", r1=0.05, r2=0.01, depth=0.35, segs=10, loc=(-0.30, 0.65, dz), parent=head_p, mat=MAT_DRAGON_HORN)
    horn_tip.rotation_euler = (math.radians(-150), 0, 0)

# 2 yeux émissifs verts
dragon_eyes = []
for side, dz in [("L", 0.28), ("R", -0.28)]:
    eye = smooth_sphere(f"eye_{side}", r=0.10, segs=16, rings=12, loc=(0.40, 0.20, dz), parent=head_p, mat=MAT_EYE)
    dragon_eyes.append(eye)
    # eye ridge above
    ridge = smooth_sphere(f"eye_ridge_{side}", r=0.13, segs=14, rings=10, loc=(0.28, 0.35, dz), parent=head_p, mat=MAT_DRAGON_DARK, scale=(1.2, 0.6, 1.0))

# 2 nostrils
for side, dz in [("L", 0.10), ("R", -0.10)]:
    nostril = smooth_sphere(f"nostril_{side}", r=0.04, segs=10, rings=8, loc=(1.15, 0.05, dz), parent=head_p, mat=MAT_DRAGON_DARK)

# upper teeth (10 visible)
for k in range(10):
    kx = 0.50 + (k % 5) * 0.10
    kz = 0.20 if k < 5 else -0.20
    tooth = smooth_cone(f"tooth_up_{k}", r1=0.04, r2=0.005, depth=0.13, segs=8, loc=(kx, -0.18, kz), parent=head_p, mat=MAT_TEETH)
    tooth.rotation_euler = (math.radians(180), 0, 0)

# lower jaw (open to breath fire)
jaw_p = empty("jaw_p", (0.30, -0.05, 0), parent=head_p)
jaw_body = smooth_sphere("jaw_body", r=0.35, segs=22, rings=14, loc=(0.40, -0.15, 0), parent=jaw_p, mat=MAT_DRAGON_BODY, scale=(1.7, 0.55, 0.95))
# 10 lower teeth
for k in range(10):
    kx = 0.30 + (k % 5) * 0.10
    kz = 0.18 if k < 5 else -0.18
    tooth_l = smooth_cone(f"tooth_lo_{k}", r1=0.035, r2=0.005, depth=0.11, segs=8, loc=(kx, 0.03, kz), parent=jaw_p, mat=MAT_TEETH)

# 2 GRANDES AILES (3 segments hiérarchiques chacune)
wings_root = []
wing_segments_all = []
for side, dz, sign in [("L", 0.65, 1), ("R", -0.65, -1)]:
    wing_root = empty(f"wing_root_{side}", (0.30, 0.45, dz), parent=dragon)
    wing_root.rotation_euler = (0, 0, math.radians(15 * sign))
    wings_root.append(wing_root)

    # Wing bone 1 (humerus - upper arm, large)
    bone1 = smooth_cone(f"wing_bone1_{side}", r1=0.10, r2=0.06, depth=1.5, segs=14, loc=(0, 0, sign * 0.75), parent=wing_root, mat=MAT_WING_BONE)
    bone1.rotation_euler = (0 if sign > 0 else math.radians(180), math.radians(0), 0)
    # Membrane 1 between body and bone 1
    membrane1 = smooth_sphere(f"wing_mem1_{side}", r=0.7, segs=16, rings=10, loc=(0, -0.15, sign * 0.75), parent=wing_root, mat=MAT_WING_MEMBRANE, scale=(0.65, 0.04, 1.5))

    # Wing pivot 2 (elbow joint)
    wing2_p = empty(f"wing2_p_{side}", (0, 0, sign * 1.50), parent=wing_root)
    wing2_p.rotation_euler = (0, math.radians(-30 * sign), 0)

    # Wing bone 2 (forearm)
    bone2 = smooth_cone(f"wing_bone2_{side}", r1=0.06, r2=0.04, depth=1.3, segs=12, loc=(0, 0, sign * 0.65), parent=wing2_p, mat=MAT_WING_BONE)
    bone2.rotation_euler = (0 if sign > 0 else math.radians(180), 0, 0)
    # Membrane 2 (3 fingers spread)
    for k in range(3):
        ka = -0.4 + k * 0.4
        # bone finger
        finger = smooth_cone(f"wing_finger_{side}_{k}", r1=0.04, r2=0.01, depth=1.2, segs=10, loc=(0, ka * 0.5, sign * 0.65), parent=wing2_p, mat=MAT_WING_BONE)
        finger.rotation_euler = (0 if sign > 0 else math.radians(180), math.radians(ka * 30 * sign), 0)
    # Membrane 2 (large fan-like)
    membrane2 = smooth_sphere(f"wing_mem2_{side}", r=1.0, segs=18, rings=14, loc=(0, -0.20, sign * 1.0), parent=wing2_p, mat=MAT_WING_MEMBRANE, scale=(0.85, 0.04, 1.8))

    wing_segments_all.append((wing_root, wing2_p))

# 4 pattes griffues (smaller, retracted while flying)
legs = []
for side, dz in [("FL", 0.55), ("FR", -0.55), ("BL", 0.55), ("BR", -0.55)]:
    dx = 0.8 if side.startswith("F") else -0.8
    leg_p = empty(f"leg_p_{side}", (dx, -0.50, dz), parent=dragon)
    leg_p.rotation_euler = (0, 0, math.radians(45))
    # thigh
    thigh = smooth_cone(f"thigh_{side}", r1=0.10, r2=0.08, depth=0.40, segs=12, loc=(0.20, 0, 0), parent=leg_p, mat=MAT_DRAGON_BODY)
    thigh.rotation_euler = (0, 0, math.radians(90))
    # shin (smaller, retracted)
    shin = smooth_cone(f"shin_{side}", r1=0.07, r2=0.05, depth=0.30, segs=12, loc=(0.40, -0.15, 0), parent=leg_p, mat=MAT_DRAGON_BODY)
    shin.rotation_euler = (math.radians(-30), 0, math.radians(90))
    # 3 claws
    for k in range(3):
        ka = -0.10 + k * 0.10
        claw = smooth_cone(f"claw_{side}_{k}", r1=0.03, r2=0.0, depth=0.10, segs=6, loc=(0.55, -0.30, ka), parent=leg_p, mat=MAT_CLAW)
        claw.rotation_euler = (math.radians(-60), 0, math.radians(90))
    legs.append(leg_p)

# tail (8 segments wave propagated)
tail_segments = []
tail_root = empty("tail_root", (-2.0, 0.05, 0), parent=dragon)
current_parent = tail_root
for j in range(8):
    seg_p = empty(f"tail_p_{j}", (-0.35, -0.02 * j, 0), parent=current_parent)
    rj = 0.40 - j * 0.04
    seg = smooth_sphere(f"tail_seg_{j}", r=rj, segs=16, rings=12, loc=(-0.15, 0, 0), parent=seg_p, mat=MAT_DRAGON_BODY, scale=(1.4, 0.85, 0.85))
    # spike on top
    spike = smooth_cone(f"tail_spike_{j}", r1=0.06, r2=0.0, depth=0.12, segs=6, loc=(-0.15, rj * 0.8, 0), parent=seg_p, mat=MAT_SCALE)
    spike.rotation_euler = (math.radians(-90), 0, 0)
    tail_segments.append(seg_p)
    current_parent = seg_p
# Tail end : arrow-shaped spike
tail_tip = smooth_cone("tail_tip", r1=0.10, r2=0.0, depth=0.40, segs=10, loc=(-0.25, 0, 0), parent=current_parent, mat=MAT_SCALE)
tail_tip.rotation_euler = (0, 0, math.radians(90))

# 2 fin-like blades on tail tip
for side, dz in [("L", 0.10), ("R", -0.10)]:
    fin = beveled_cube(f"tail_fin_{side}", (0.30, 0.04, 0.18), bevel_offset=0.04, bevel_segments=2, loc=(-0.30, 0, dz), parent=current_parent, mat=MAT_DRAGON_DARK)

# --- FLAMMES émissives crachées (8 segments forming flame jet) ----------
flame_p = empty("flame_p", (1.15, -0.15, 0), parent=head_p)
flame_segments = []
for k in range(8):
    t = k / 7
    fx = 0.3 + t * 1.8
    fr_base = 0.22 - t * 0.12
    # alternate flame types
    if k % 3 == 0:
        mat = MAT_FIRE_CORE
    elif k % 3 == 1:
        mat = MAT_FIRE
    else:
        mat = MAT_FIRE_TIP
    seg = smooth_sphere(f"flame_seg_{k}", r=fr_base, segs=14, rings=10, loc=(fx, 0, 0), parent=flame_p, mat=mat, scale=(1.5, 1.0, 1.0))
    flame_segments.append(seg)

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

# dragon flying : circular path with banking
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 2.0
    cx = math.cos(angle) * 5.0
    cz = math.sin(angle) * 3.0
    cy = 6.0 + math.sin(tt * math.pi * 4.0) * 0.3  # vertical bob
    kf_loc(dragon, f, (cx, cy, cz))
    # heading aligned with motion
    heading = -angle + math.pi / 2
    bank = math.radians(15) * math.sin(angle)
    pitch = math.radians(5) * math.cos(tt * math.pi * 3.0)
    kf_rot(dragon, f, (pitch, heading, bank))

# 2 wings flap synchronized
for i, wing_root in enumerate(wings_root):
    sign = 1 if i == 0 else -1
    base_rot = wing_root.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        flap = math.radians(35) * math.sin(tt * math.pi * 6.0)  # 3 flaps per loop
        kf_rot(wing_root, f, (flap * sign, 0, base_rot[2]))

# head tilts looking around
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    head_x = math.radians(8) * math.sin(tt * math.pi * 3.0)
    head_z = math.radians(-15) + math.radians(15) * math.cos(tt * math.pi * 2.5)
    kf_rot(head_p, f, (head_x, 0, head_z))

# jaw opens for breathing fire
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    # Cycle : closed → breathing fire (open wide) → closed
    angle = math.radians(35) * max(0, math.sin(tt * math.pi * 3.0))
    kf_rot(jaw_p, f, (0, 0, -angle))

# 2 eyes pulse intense green
for eye in dragon_eyes:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 8.0)
        kf_scale(eye, f, (s, s, s))

# 8 flame segments pulse intense (synchronized with jaw open)
for k, seg in enumerate(flame_segments):
    base_x = seg.location.x
    base_r = 0.22 - (k / 7) * 0.12
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # active when jaw is open
        jaw_open = max(0, math.sin(tt * math.pi * 3.0))
        # base scale follows jaw, with high-frequency flicker
        s = (0.3 + jaw_open * 1.5) * (1.0 + 0.20 * math.sin(tt * math.pi * 18.0 + k * 0.5))
        kf_scale(seg, f, (1.5 * s, s, s))
        # slight drift forward in flame jet
        kf_loc(seg, f, (base_x + jaw_open * 0.3, 0, 0))

# 8 tail segments wave propagated swish
for j, seg_p in enumerate(tail_segments):
    phase = j * 0.5
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.radians(18) * math.sin(tt * math.pi * 4.0 - phase)
        kf_rot(seg_p, f, (0, wave, 0))

# clouds drift slow
for i in range(4):
    cl = bpy.data.objects.get(f"cloud_{i}")
    if cl:
        base_x = cl.location.x
        base_z = cl.location.z
        for f in range(1, FRAMES + 1, 5):
            tt = (f - 1) / (FRAMES - 1)
            dx = base_x + 0.4 * math.sin(tt * math.pi * 1.5 + i * 0.5)
            dz = base_z + 0.3 * math.cos(tt * math.pi * 1.2 + i * 0.4)
            kf_loc(cl, f, (dx, cl.location.y, dz))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_dragon_flying] wrote {OUT}")
