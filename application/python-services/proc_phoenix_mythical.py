"""
proc_phoenix_mythical.py — 150e procédural AuroraIA, MILESTONE 150 — Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Phoenix mythologique en flammes :
- corps oiseau fantasy bevelé
- 2 ailes énormes membraneuses orange/rouge avec 5 feathers each
- queue 6 segments avec traîne de feu
- tête couronnée
- 2 yeux émissifs dorés
- bec doré + serres dorées
- 30 plumes flammes individuelles autour corps
- halo doré derrière phoenix
- 12 étincelles orbites
- arbre cendres mort
- ciel coucher sang
- 4 cendres flottantes
- montagnes feu background

Animations multi-axes :
- phoenix : circular flight + bank + altitude
- 2 ailes : flap synchronized avec feathers spread
- queue 6 segs : wave propagated swish
- plumes flames : pulse cyclic individual
- 12 étincelles : orbites + scale pulse
- halo : breathe
- eyes : pulse intense doré

Sortie : output/3d/pbr_phoenix_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_phoenix_proc.glb"))

random.seed(0xCAFEFA)

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
MAT_SKY = make_mat("sky_blood", (0.55, 0.10, 0.10), roughness=1.0, emi=(0.55, 0.10, 0.10), emi_strength=0.8)
MAT_SKY_TOP = make_mat("sky_top", (0.25, 0.05, 0.10), roughness=1.0, emi=(0.30, 0.05, 0.10), emi_strength=0.5)
MAT_MOUNT_FIRE = make_mat("mount_fire", (0.30, 0.08, 0.05), roughness=0.85, emi=(0.50, 0.15, 0.05), emi_strength=0.6)
MAT_PHOENIX_BODY = make_mat("phoenix_body", (1.0, 0.45, 0.10), roughness=0.20, metallic=0.30, emi=(1.0, 0.40, 0.05), emi_strength=4.0)
MAT_PHOENIX_DARK = make_mat("phoenix_dark", (0.55, 0.20, 0.05), roughness=0.30, metallic=0.40, emi=(0.55, 0.15, 0.03), emi_strength=2.0)
MAT_FEATHER_TIP = make_mat("feather_tip", (1.0, 0.95, 0.40), roughness=0.0, alpha=0.85, emi=(1.0, 0.95, 0.40), emi_strength=12.0)
MAT_FEATHER_MID = make_mat("feather_mid", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=10.0)
MAT_FEATHER_BASE = make_mat("feather_base", (0.75, 0.15, 0.05), roughness=0.20, emi=(0.75, 0.15, 0.05), emi_strength=6.0)
MAT_GOLD = make_mat("gold", (1.0, 0.85, 0.30), metallic=0.95, roughness=0.10, emi=(0.70, 0.55, 0.10), emi_strength=1.0)
MAT_GOLD_BRIGHT = make_mat("gold_bright", (1.0, 0.95, 0.50), roughness=0.0, emi=(1.0, 0.95, 0.50), emi_strength=8.0)
MAT_EYE_GOLD = make_mat("eye_gold", (1.0, 0.90, 0.30), roughness=0.0, emi=(1.0, 0.90, 0.30), emi_strength=14.0)
MAT_HALO = make_mat("halo", (1.0, 0.85, 0.20), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.20), emi_strength=5.0)
MAT_SPARK = make_mat("spark", (1.0, 0.95, 0.45), roughness=0.0, emi=(1.0, 0.95, 0.45), emi_strength=10.0)
MAT_ASH_TREE = make_mat("ash_tree", (0.08, 0.06, 0.05), roughness=0.95)
MAT_ASH = make_mat("ash", (0.45, 0.40, 0.35), roughness=0.85, alpha=0.6, emi=(0.50, 0.30, 0.20), emi_strength=1.0)
MAT_GROUND = make_mat("ground", (0.15, 0.08, 0.06), roughness=0.95, emi=(0.20, 0.05, 0.03), emi_strength=0.3)

# --- backdrop : blood sunset sky ---------------------------------------
sky_top = beveled_cube("sky_top", (40, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 12), mat=MAT_SKY_TOP)
sky_low = beveled_cube("sky_low", (40, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 4), mat=MAT_SKY)

# 3 fire mountains
for i, (mx, mh, mw) in enumerate([(-9, 5, 6), (9, 6, 5), (0, 4, 5)]):
    mp = empty(f"mount_{i}", (mx, 0, 10))
    m = smooth_cone(f"mount_{i}_body", r1=mw, r2=0.4, depth=mh, segs=14, loc=(0, mh / 2, 0), parent=mp, mat=MAT_MOUNT_FIRE)
    m.rotation_euler = (math.radians(90), 0, 0)

# Ground (charred)
ground = beveled_cube("ground", (30, 0.1, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND)

# Dead ash tree
tree_p = empty("ash_tree_p", (-7, 0, 5))
trunk = smooth_cone("ash_trunk", r1=0.30, r2=0.15, depth=4.0, segs=12, loc=(0, 2.0, 0), parent=tree_p, mat=MAT_ASH_TREE)
trunk.rotation_euler = (math.radians(90), 0, 0)
# 6 bare branches
for j in range(6):
    ja = j * (math.pi * 2 / 6)
    branch = smooth_cone(f"ash_branch_{j}", r1=0.08, r2=0.02, depth=1.5, segs=8, loc=(0, 3.5, 0), parent=tree_p, mat=MAT_ASH_TREE)
    branch.rotation_euler = (math.radians(60), 0, ja)

# --- PHOENIX ----------------------------------------------------------
phoenix = empty("phoenix", (0, 6.5, 0))

# Body (stretched sphere)
def make_body(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.55)
    bmesh.ops.scale(bm, vec=(1.6, 1.0, 1.0), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0, 0)
    me.materials.append(MAT_PHOENIX_BODY)
    smooth_shade(me)
    return o

body = make_body("phoenix_body_main", phoenix)

# Neck
neck = smooth_cone("phoenix_neck", r1=0.35, r2=0.25, depth=0.50, segs=18, loc=(0.85, 0.20, 0), parent=phoenix, mat=MAT_PHOENIX_BODY)
neck.rotation_euler = (0, 0, math.radians(-50))

# Head
head_p = empty("phoenix_head_p", (1.20, 0.55, 0), parent=phoenix)
head = smooth_sphere("phoenix_head", r=0.30, segs=24, rings=18, loc=(0, 0, 0), parent=head_p, mat=MAT_PHOENIX_BODY, scale=(1.4, 1.0, 1.0))

# Beak (gold pointed)
beak = smooth_cone("phoenix_beak", r1=0.10, r2=0.0, depth=0.30, segs=14, loc=(0.30, -0.05, 0), parent=head_p, mat=MAT_GOLD_BRIGHT)
beak.rotation_euler = (0, math.radians(90), 0)

# Crown (5 gold spikes on head)
for k in range(5):
    a = math.radians(-40 + k * 20)
    spike = smooth_cone(f"phoenix_crown_{k}", r1=0.04, r2=0.0, depth=0.25, segs=8, loc=(-0.10 + 0.05 * k, 0.30, 0), parent=head_p, mat=MAT_GOLD_BRIGHT)
    spike.rotation_euler = (a, 0, math.radians(-30))

# 2 eyes (intense gold)
phoenix_eyes = []
for side, dz in [("L", 0.13), ("R", -0.13)]:
    eye = smooth_sphere(f"eye_{side}", r=0.07, segs=16, rings=12, loc=(0.18, 0.10, dz), parent=head_p, mat=MAT_EYE_GOLD)
    phoenix_eyes.append(eye)

# Eye rings (dark feathers around)
for side, dz in [("L", 0.13), ("R", -0.13)]:
    ring = smooth_sphere(f"eye_ring_{side}", r=0.10, segs=14, rings=10, loc=(0.16, 0.10, dz), parent=head_p, mat=MAT_PHOENIX_DARK, scale=(1.0, 1.0, 0.5))

# --- 2 GRANDES AILES (3 segments hiérarchiques + 5 feathers chacune) ---
wings_root = []
all_feathers = []
for side, sign in [("L", 1), ("R", -1)]:
    wing_root = empty(f"wing_root_{side}", (0.20, 0.20, 0.40 * sign), parent=phoenix)
    wing_root.rotation_euler = (0, 0, math.radians(10 * sign))

    # Wing bone segments
    bone1 = smooth_cone(f"wing_bone1_{side}", r1=0.08, r2=0.05, depth=1.2, segs=12, loc=(0, 0, sign * 0.6), parent=wing_root, mat=MAT_PHOENIX_BODY)
    bone1.rotation_euler = (0 if sign > 0 else math.radians(180), 0, 0)

    wing2_p = empty(f"wing2_p_{side}", (0, 0, sign * 1.20), parent=wing_root)
    wing2_p.rotation_euler = (0, math.radians(-25 * sign), 0)

    bone2 = smooth_cone(f"wing_bone2_{side}", r1=0.05, r2=0.03, depth=1.0, segs=10, loc=(0, 0, sign * 0.5), parent=wing2_p, mat=MAT_PHOENIX_BODY)
    bone2.rotation_euler = (0 if sign > 0 else math.radians(180), 0, 0)

    # 5 feathers (large flame plumes) cascading
    for k in range(5):
        t = k / 4
        # finger bone
        finger_a = math.radians(-25 + k * 12)
        # feather as multiple cones (base + mid + tip with different colors)
        feather_p = empty(f"feather_p_{side}_{k}", (0, 0.10, sign * (0.20 + t * 0.80)), parent=wing2_p)
        feather_p.rotation_euler = (0 if sign > 0 else math.radians(180), 0, finger_a)
        # feather base (red)
        f_base = smooth_cone(f"feather_b_{side}_{k}", r1=0.07, r2=0.04, depth=0.30, segs=10, loc=(0, 0, sign * 0.15), parent=feather_p, mat=MAT_FEATHER_BASE)
        f_base.rotation_euler = (math.radians(90 if sign > 0 else -90), 0, 0)
        # feather mid (orange)
        f_mid = smooth_cone(f"feather_m_{side}_{k}", r1=0.04, r2=0.025, depth=0.40, segs=10, loc=(0, 0, sign * 0.55), parent=feather_p, mat=MAT_FEATHER_MID)
        f_mid.rotation_euler = (math.radians(90 if sign > 0 else -90), 0, 0)
        # feather tip (yellow flame)
        f_tip = smooth_cone(f"feather_t_{side}_{k}", r1=0.025, r2=0.0, depth=0.50, segs=10, loc=(0, 0, sign * 1.05), parent=feather_p, mat=MAT_FEATHER_TIP)
        f_tip.rotation_euler = (math.radians(90 if sign > 0 else -90), 0, 0)
        all_feathers.append((f_tip, k, side))

    wings_root.append(wing_root)

# --- Queue 6 segments + traîne de feu ---
tail_segments = []
tail_root = empty("tail_root", (-0.85, 0.10, 0), parent=phoenix)
current_parent = tail_root
for j in range(6):
    seg_p = empty(f"tail_p_{j}", (-0.25, -0.02 * j, 0), parent=current_parent)
    rj = 0.18 - j * 0.02
    seg = smooth_sphere(f"tail_seg_{j}", r=rj, segs=14, rings=10, loc=(-0.10, 0, 0), parent=seg_p, mat=MAT_FEATHER_BASE, scale=(1.5, 0.7, 0.7))
    # feather tip (one per segment, growing)
    tip = smooth_cone(f"tail_tip_{j}", r1=0.04, r2=0.0, depth=0.4 + j * 0.05, segs=10, loc=(-0.20, 0, 0), parent=seg_p, mat=MAT_FEATHER_MID if j % 2 == 0 else MAT_FEATHER_TIP)
    tip.rotation_euler = (0, 0, math.radians(90))
    tail_segments.append(seg_p)
    current_parent = seg_p

# Tail final flame burst (long cone trail)
trail_p = empty("trail_p", (-0.30, 0, 0), parent=current_parent)
trail_main = smooth_cone("trail_main", r1=0.10, r2=0.0, depth=0.8, segs=14, loc=(-0.40, 0, 0), parent=trail_p, mat=MAT_FEATHER_TIP)
trail_main.rotation_euler = (0, 0, math.radians(90))

# --- 4 serres (claws) gold ---
for side, dz in [("L", 0.15), ("R", -0.15)]:
    leg_p = empty(f"leg_p_{side}", (-0.1, -0.45, dz), parent=phoenix)
    thigh = smooth_cone(f"thigh_{side}", r1=0.08, r2=0.06, depth=0.20, segs=10, loc=(0, -0.10, 0), parent=leg_p, mat=MAT_PHOENIX_DARK)
    shin = smooth_cone(f"shin_{side}", r1=0.05, r2=0.04, depth=0.18, segs=10, loc=(0.05, -0.28, 0), parent=leg_p, mat=MAT_GOLD)
    # 3 claws curling
    for k in range(3):
        ka = -0.10 + k * 0.10
        claw = smooth_cone(f"claw_{side}_{k}", r1=0.025, r2=0.0, depth=0.08, segs=6, loc=(0.10, -0.40, ka), parent=leg_p, mat=MAT_GOLD_BRIGHT)
        claw.rotation_euler = (math.radians(-60), 0, math.radians(90))

# --- 30 plumes flammes individuelles autour corps ---
flame_plumes = []
for i in range(30):
    a = random.uniform(0, math.pi * 2)
    elev = random.uniform(-0.3, 0.4)
    r = 0.7 + random.uniform(-0.1, 0.2)
    px = math.cos(a) * r
    py = elev
    pz = math.sin(a) * r * 0.5
    mat = random.choice([MAT_FEATHER_BASE, MAT_FEATHER_MID, MAT_FEATHER_TIP])
    plume = smooth_cone(f"plume_{i}", r1=0.05, r2=0.0, depth=0.25, segs=8, loc=(px, py, pz), parent=phoenix, mat=mat)
    # orient outward
    plume.rotation_euler = (math.radians(90), 0, -a)
    flame_plumes.append((plume, i))

# --- halo doré derrière phoenix ---
halo_p = empty("halo_p", (-0.20, 0.40, 0), parent=phoenix)
halo = smooth_cone("halo_main", r1=1.2, r2=1.2, depth=0.08, segs=32, loc=(0, 0, 0), parent=halo_p, mat=MAT_HALO)
halo.rotation_euler = (0, math.radians(90), 0)
halo.scale = (1.0, 0.05, 1.0)

# --- 12 étincelles orbites ---
sparks = []
for i in range(12):
    a = i * (math.pi * 2 / 12)
    sr = 1.5
    sx = math.cos(a) * sr
    sy = math.sin(a * 2) * 0.3
    sz = math.sin(a) * sr
    sp = smooth_sphere(f"spark_{i}", r=0.06, segs=12, rings=8, loc=(sx, sy, sz), parent=phoenix, mat=MAT_SPARK)
    sparks.append((sp, i, a))

# --- 4 cendres flottantes (in scene, not parented to phoenix) ---
ash_drifts = []
for i in range(4):
    ax = random.uniform(-6, 6)
    ay = random.uniform(3, 8)
    az = random.uniform(-5, 5)
    a = smooth_sphere(f"ash_drift_{i}", r=0.12, segs=12, rings=8, loc=(ax, ay, az), mat=MAT_ASH, scale=(1.0, 0.5, 1.0))
    ash_drifts.append((a, ax, ay, az))

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

# Phoenix : circular flight path with banking
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 2.0
    cx = math.cos(angle) * 5.0
    cz = math.sin(angle) * 3.0
    cy = 6.5 + math.sin(tt * math.pi * 4.0) * 0.4
    kf_loc(phoenix, f, (cx, cy, cz))
    heading = -angle + math.pi / 2
    bank = math.radians(20) * math.sin(angle)
    pitch = math.radians(5) * math.cos(tt * math.pi * 3.0)
    kf_rot(phoenix, f, (pitch, heading, bank))

# 2 wings flap synchronized + spread feathers
for i, wing_root in enumerate(wings_root):
    sign = 1 if i == 0 else -1
    base_rot = wing_root.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        flap = math.radians(40) * math.sin(tt * math.pi * 7.0)  # 3.5 flaps per loop
        kf_rot(wing_root, f, (flap * sign, 0, base_rot[2]))

# Head turn + bob
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    head_x = math.radians(8) * math.sin(tt * math.pi * 3.0)
    head_y = math.radians(10) * math.cos(tt * math.pi * 2.5)
    kf_rot(head_p, f, (head_x, head_y, 0))

# 2 eyes pulse intense gold
for eye in phoenix_eyes:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 8.0)
        kf_scale(eye, f, (s, s, s))

# 6 tail segments wave propagated swish
for j, seg_p in enumerate(tail_segments):
    phase = j * 0.5
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        wave = math.radians(20) * math.sin(tt * math.pi * 5.0 - phase)
        kf_rot(seg_p, f, (wave * 0.3, wave, 0))

# 30 plumes pulse cyclic (high-frequency, phase offset)
for plume, idx in flame_plumes:
    phase = idx * 0.3
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.40 * math.sin(tt * math.pi * 12.0 + phase)
        kf_scale(plume, f, (s, s, s))

# 10 feather tips pulse (front 5 + back 5 of each wing fan)
for tip, k, side in all_feathers:
    phase = k * 0.4 + (0 if side == "L" else math.pi / 2)
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 10.0 + phase)
        kf_scale(tip, f, (s, s, s))

# Halo breathe + slow rotate
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.15 * math.sin(tt * math.pi * 3.0)
    kf_scale(halo, f, (s, 0.05, s))
    rotZ = tt * math.pi * 0.5  # slow rotation
    kf_rot(halo_p, f, (0, math.radians(90), rotZ))

# 12 sparks orbit + pulse
for sp, idx, a0 in sparks:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        a = a0 + tt * math.pi * 4.0
        sr = 1.5 + 0.2 * math.sin(tt * math.pi * 4.0 + a0)
        sx = math.cos(a) * sr
        sy = math.sin(a * 2) * 0.3
        sz = math.sin(a) * sr
        kf_loc(sp, f, (sx, sy, sz))
        s = 1.0 + 0.50 * math.sin(tt * math.pi * 10.0 + a0)
        kf_scale(sp, f, (s, s, s))

# 4 cendres flottantes (slow drift)
for a, ax, ay, az, in [(a[0], a[1], a[2], a[3]) for a in ash_drifts]:
    pass  # handled below

for ash_obj, ax, ay, az in ash_drifts:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        dx = ax + 0.4 * math.sin(tt * math.pi * 1.5 + ax)
        dy = ay + 0.3 * math.sin(tt * math.pi * 2.0 + ay)
        dz = az + 0.4 * math.cos(tt * math.pi * 1.2 + az)
        kf_loc(ash_obj, f, (dx, dy, dz))
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 3.0 + ax)
        kf_scale(ash_obj, f, (s, 0.5 * s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_phoenix] wrote {OUT}")
