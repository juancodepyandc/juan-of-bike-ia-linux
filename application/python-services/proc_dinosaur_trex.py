"""
proc_dinosaur_trex.py — 142e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axis anim).

T-Rex géant smooth shaded :
- corps profilé bevelé (sphère étirée)
- tête énorme avec mâchoire articulée
- 2 yeux émissifs rouges
- 2 bras minuscules (typique T-Rex)
- 2 jambes énormes musclées avec orteils
- queue longue 6 segments articulée (anim swish)
- 30 dents pointues (15 supérieures + 15 inférieures)
- langue rouge
- paysage jurassic préhistorique
- 3 fougères + 2 arbres préhistoriques
- 2 petits dinos (vélociraptors)
- volcan en éruption au loin avec lave
- ciel orageux

Animations multi-axes simultanées :
- T-Rex : marche cyclique (jambes alternance + body bob + queue swish)
- tête : tourne + head bob
- mâchoire : ouverture/fermeture cyclique
- 2 yeux : pulse intense rouge
- 6 segments queue : swish wave-like
- fougères sway
- 2 petits dinos head bob + drift
- volcan : flame intense pulse

Sortie : output/3d/pbr_trex_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_trex_proc.glb"))

random.seed(0xCAFE73)

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
MAT_SKY = make_mat("sky_storm", (0.30, 0.25, 0.30), roughness=1.0,
                    emi=(0.20, 0.18, 0.25), emi_strength=0.5)
MAT_SKY_TOP = make_mat("sky_top", (0.45, 0.35, 0.45), roughness=1.0,
                         emi=(0.30, 0.25, 0.35), emi_strength=0.4)
MAT_GROUND = make_mat("ground", (0.40, 0.30, 0.20), roughness=0.95)
MAT_GRASS = make_mat("grass", (0.30, 0.45, 0.18), roughness=0.85)
MAT_TREX_BODY = make_mat("trex_body", (0.30, 0.40, 0.25), roughness=0.65,
                          emi=(0.08, 0.10, 0.06), emi_strength=0.15)
MAT_TREX_BELLY = make_mat("trex_belly", (0.55, 0.50, 0.30), roughness=0.6,
                            emi=(0.15, 0.13, 0.08), emi_strength=0.15)
MAT_TREX_DARK = make_mat("trex_dark", (0.20, 0.25, 0.15), roughness=0.7)
MAT_TREX_TEETH = make_mat("teeth", (0.92, 0.90, 0.85), roughness=0.4,
                            emi=(0.40, 0.40, 0.35), emi_strength=0.4)
MAT_TREX_EYE = make_mat("trex_eye", (1.0, 0.15, 0.10), roughness=0.0,
                          emi=(1.0, 0.15, 0.10), emi_strength=8.0)
MAT_TONGUE = make_mat("tongue", (0.85, 0.20, 0.30), roughness=0.5,
                        emi=(0.35, 0.05, 0.08), emi_strength=0.4)
MAT_CLAW = make_mat("claw", (0.15, 0.10, 0.08), roughness=0.5,
                      emi=(0.05, 0.03, 0.02), emi_strength=0.2)
MAT_FERN = make_mat("fern", (0.15, 0.55, 0.25), roughness=0.85,
                      emi=(0.05, 0.25, 0.10), emi_strength=0.3)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.25, 0.15, 0.08), roughness=0.9)
MAT_TREE_LEAVES = make_mat("tree_leaves", (0.20, 0.50, 0.20), roughness=0.85,
                             emi=(0.08, 0.20, 0.08), emi_strength=0.3)
MAT_RAPTOR_BODY = make_mat("raptor_body", (0.60, 0.30, 0.20), roughness=0.65,
                             emi=(0.20, 0.10, 0.05), emi_strength=0.2)
MAT_VOLCANO_DARK = make_mat("volcano_dark", (0.15, 0.12, 0.10), roughness=0.9)
MAT_LAVA = make_mat("lava", (1.0, 0.45, 0.05), roughness=0.3,
                      emi=(1.0, 0.45, 0.05), emi_strength=8.0)
MAT_LAVA_HOT = make_mat("lava_hot", (1.0, 0.85, 0.20), roughness=0.2,
                          emi=(1.0, 0.85, 0.20), emi_strength=12.0)
MAT_SMOKE = make_mat("smoke", (0.40, 0.35, 0.40), roughness=1.0, alpha=0.65,
                       emi=(0.25, 0.22, 0.28), emi_strength=0.4)

# --- backdrop : stormy sky ----------------------------------------------
sky_top = beveled_cube("sky_top", (40, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 12), mat=MAT_SKY_TOP)
sky_bot = beveled_cube("sky_bot", (40, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 4), mat=MAT_SKY)

# --- ground -------------------------------------------------------------
ground = beveled_cube("ground", (35, 0.1, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND)
# grass patches
for i in range(8):
    gx = random.uniform(-12, 12)
    gz = random.uniform(-8, 8)
    g = beveled_cube(f"grass_patch_{i}", (random.uniform(1.5, 3.0), 0.05, random.uniform(1.0, 2.0)), bevel_offset=0.03, bevel_segments=2, loc=(gx, 0.01, gz), mat=MAT_GRASS)

# --- T-Rex --------------------------------------------------------------
trex = empty("trex", (0, 2.5, 0))

# main body (sphère étirée smooth)
def make_body(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.9)
    bmesh.ops.scale(bm, vec=(2.2, 1.0, 1.0), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0, 0)
    me.materials.append(MAT_TREX_BODY)
    smooth_shade(me)
    return o

body = make_body("trex_body_main", trex)

# belly (lighter underbelly)
belly = smooth_sphere("trex_belly", r=0.7, segs=24, rings=18, loc=(0, -0.40, 0), parent=trex, mat=MAT_TREX_BELLY, scale=(2.5, 0.4, 1.1))

# neck (curving forward up)
neck_p = empty("neck_p", (1.5, 0.55, 0), parent=trex)
neck_p.rotation_euler = (0, 0, math.radians(-35))
# 3 neck segments smoothly tapered
for j in range(3):
    h = 0.20 + j * 0.30
    rj = 0.45 - j * 0.05
    seg = smooth_cone(f"neck_seg_{j}", r1=rj, r2=rj * 0.85, depth=0.40, segs=18, loc=(0, h, 0), parent=neck_p, mat=MAT_TREX_BODY)
    seg.rotation_euler = (math.radians(90), 0, 0)

# head ---------------------------------------------------------------
head_p = empty("head_p", (1.65, 1.65, 0), parent=trex)
head_p.rotation_euler = (0, 0, math.radians(-10))
# upper skull (large)
upper_head = smooth_sphere("upper_head", r=0.50, segs=28, rings=18, loc=(0.30, 0.10, 0), parent=head_p, mat=MAT_TREX_BODY, scale=(1.8, 1.0, 1.0))
# snout extension (front)
snout = smooth_cone("snout", r1=0.40, r2=0.20, depth=0.55, segs=20, loc=(0.85, 0.05, 0), parent=head_p, mat=MAT_TREX_BODY)
snout.rotation_euler = (0, math.radians(90), 0)
snout.scale = (1.0, 1.0, 0.9)
# eye ridges (bumps above eyes)
for side, dz in [("L", 0.32), ("R", -0.32)]:
    ridge = smooth_sphere(f"eye_ridge_{side}", r=0.12, segs=14, rings=10, loc=(0.35, 0.30, dz), parent=head_p, mat=MAT_TREX_DARK, scale=(1.2, 0.6, 1.0))
# 2 eyes émissifs rouges
trex_eyes = []
for side, dz in [("L", 0.30), ("R", -0.30)]:
    eye = smooth_sphere(f"trex_eye_{side}", r=0.08, segs=14, rings=10, loc=(0.50, 0.20, dz), parent=head_p, mat=MAT_TREX_EYE)
    trex_eyes.append(eye)
# 2 nostrils (small darker spheres)
for side, dz in [("L", 0.08), ("R", -0.08)]:
    nostril = smooth_sphere(f"nostril_{side}", r=0.04, segs=10, rings=8, loc=(1.10, 0.08, dz), parent=head_p, mat=MAT_TREX_DARK)

# upper jaw (visible part containing teeth - same as head, teeth go below)
# 15 upper teeth (cones pointing down from snout)
for k in range(15):
    kx = 0.40 + (k % 8) * 0.10
    kz = 0.25 if k < 8 else -0.25
    tooth = smooth_cone(f"tooth_up_{k}", r1=0.04, r2=0.005, depth=0.13, segs=8, loc=(kx, -0.15, kz), parent=head_p, mat=MAT_TREX_TEETH)
    tooth.rotation_euler = (math.radians(180), 0, math.radians(random.uniform(-10, 10)))

# lower jaw (animated open/close)
jaw_p = empty("jaw_p", (0.30, -0.10, 0), parent=head_p)
jaw_body = smooth_sphere("jaw_body", r=0.40, segs=24, rings=16, loc=(0.40, -0.10, 0), parent=jaw_p, mat=MAT_TREX_BODY, scale=(1.7, 0.5, 0.95))
# 15 lower teeth
for k in range(15):
    kx = 0.30 + (k % 8) * 0.10
    kz = 0.22 if k < 8 else -0.22
    tooth_l = smooth_cone(f"tooth_lo_{k}", r1=0.035, r2=0.005, depth=0.11, segs=8, loc=(kx, 0.05, kz), parent=jaw_p, mat=MAT_TREX_TEETH)
    tooth_l.rotation_euler = (0, 0, math.radians(random.uniform(-10, 10)))
# tongue
tongue = smooth_sphere("tongue", r=0.10, segs=14, rings=10, loc=(0.50, -0.05, 0), parent=jaw_p, mat=MAT_TONGUE, scale=(2.0, 0.3, 1.0))

# --- 2 small arms (typical T-Rex) ---------------------------------
arms = []
for side, dz in [("L", 0.50), ("R", -0.50)]:
    arm_p = empty(f"arm_p_{side}", (0.40, -0.10, dz), parent=trex)
    arm_p.rotation_euler = (0, 0, math.radians(-30))
    # upper arm
    upper = smooth_cone(f"arm_upper_{side}", r1=0.12, r2=0.10, depth=0.40, segs=12, loc=(0.20, 0, 0), parent=arm_p, mat=MAT_TREX_BODY)
    upper.rotation_euler = (0, 0, math.radians(90))
    # forearm
    forearm_p = empty(f"forearm_p_{side}", (0.40, 0, 0), parent=arm_p)
    forearm_p.rotation_euler = (0, 0, math.radians(-50))
    forearm = smooth_cone(f"forearm_{side}", r1=0.09, r2=0.07, depth=0.30, segs=12, loc=(0.15, 0, 0), parent=forearm_p, mat=MAT_TREX_BODY)
    forearm.rotation_euler = (0, 0, math.radians(90))
    # 2 small claws
    for k in range(2):
        claw = smooth_cone(f"claw_{side}_{k}", r1=0.04, r2=0.0, depth=0.10, segs=6, loc=(0.32, -0.04 if k == 0 else 0.04, 0), parent=forearm_p, mat=MAT_CLAW)
        claw.rotation_euler = (0, 0, math.radians(90))
    arms.append(arm_p)

# --- 2 huge legs (powerful) ---------------------------------------
legs = []
for side, dz in [("L", 0.50), ("R", -0.50)]:
    leg_p = empty(f"leg_p_{side}", (-0.30, -0.80, dz), parent=trex)
    # thigh (large)
    thigh = smooth_sphere(f"thigh_{side}", r=0.35, segs=20, rings=14, loc=(0, -0.30, 0), parent=leg_p, mat=MAT_TREX_BODY, scale=(1.0, 1.5, 1.0))
    # shin
    shin = smooth_cone(f"shin_{side}", r1=0.18, r2=0.14, depth=0.7, segs=14, loc=(0, -1.05, 0), parent=leg_p, mat=MAT_TREX_BODY)
    shin.rotation_euler = (math.radians(90), 0, 0)
    # ankle joint
    ankle = smooth_sphere(f"ankle_{side}", r=0.14, segs=12, rings=10, loc=(0, -1.50, 0), parent=leg_p, mat=MAT_TREX_DARK)
    # foot (with 3 toes + claws)
    foot_base = smooth_sphere(f"foot_{side}", r=0.20, segs=14, rings=10, loc=(0.20, -1.65, 0), parent=leg_p, mat=MAT_TREX_BODY, scale=(1.5, 0.5, 1.0))
    # 3 toes with claws
    for k in range(3):
        kz = -0.15 + k * 0.15
        toe = smooth_cone(f"toe_{side}_{k}", r1=0.05, r2=0.03, depth=0.20, segs=8, loc=(0.40, -1.68, kz), parent=leg_p, mat=MAT_TREX_BODY)
        toe.rotation_euler = (0, 0, math.radians(90))
        # claw at tip
        claw = smooth_cone(f"toe_claw_{side}_{k}", r1=0.025, r2=0.0, depth=0.10, segs=6, loc=(0.55, -1.70, kz), parent=leg_p, mat=MAT_CLAW)
        claw.rotation_euler = (0, 0, math.radians(90))
    legs.append(leg_p)

# --- tail (long, 6 segments articulated) ---------------------------------
tail_segments = []
tail_root = empty("tail_root", (-1.85, 0.05, 0), parent=trex)
current_parent = tail_root
for j in range(6):
    seg_p = empty(f"tail_p_{j}", (-0.45, -0.05 * j, 0), parent=current_parent)
    rj = 0.35 - j * 0.045
    seg = smooth_sphere(f"tail_seg_{j}", r=rj, segs=18, rings=12, loc=(-0.20, 0, 0), parent=seg_p, mat=MAT_TREX_BODY, scale=(1.4, 0.85, 0.85))
    # body spikes on top
    spike = smooth_cone(f"tail_spike_{j}", r1=0.06, r2=0.0, depth=0.10, segs=6, loc=(-0.20, rj * 0.8, 0), parent=seg_p, mat=MAT_TREX_DARK)
    spike.rotation_euler = (math.radians(-90), 0, 0)
    tail_segments.append(seg_p)
    current_parent = seg_p

# body spikes along back (visible row)
for j in range(5):
    spike = smooth_cone(f"back_spike_{j}", r1=0.07, r2=0.0, depth=0.15, segs=6, loc=(-1.5 + j * 0.55, 0.90, 0), parent=trex, mat=MAT_TREX_DARK)
    spike.rotation_euler = (math.radians(-90), 0, 0)

# --- 3 fougères --------------------------------------------------
ferns = []
fern_locs = [(-7, -1), (7, 2), (-6, 4)]
for i, (fx, fz) in enumerate(fern_locs):
    fp = empty(f"fern_{i}", (fx, 0, fz))
    # 6 fronds radiating
    for j in range(6):
        ja = j * (math.pi * 2 / 6) + random.uniform(-0.3, 0.3)
        h = random.uniform(0.6, 1.0)
        frond = smooth_sphere(f"fern_{i}_f_{j}", r=0.20, segs=14, rings=8, loc=(math.cos(ja) * 0.25, 0.5 + h / 2, math.sin(ja) * 0.25), parent=fp, mat=MAT_FERN, scale=(1.0, 3.5 * h, 0.35))
        frond.rotation_euler = (math.radians(-25), -ja, 0)
    ferns.append(fp)

# --- 2 arbres préhistoriques --------------------------------------
for i, (tx, tz) in enumerate([(-9, -4), (9, -4)]):
    tp = empty(f"tree_{i}", (tx, 0, tz))
    trunk = smooth_cone(f"tree_{i}_trunk", r1=0.35, r2=0.25, depth=3.5, segs=14, loc=(0, 1.75, 0), parent=tp, mat=MAT_TREE_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # foliage : multiple sphere blobs forming a canopy
    for j in range(7):
        ja = j * (math.pi * 2 / 7)
        f = smooth_sphere(f"tree_{i}_f_{j}", r=0.9, segs=20, rings=14, loc=(math.cos(ja) * 0.8, 4.0 + random.uniform(-0.3, 0.3), math.sin(ja) * 0.8), parent=tp, mat=MAT_TREE_LEAVES, scale=(1.3, 1.0, 1.3))

# --- 2 petits dinos (raptors) ---------------------------------------
raptors = []
def make_raptor(name, x, z, rot=0):
    p = empty(name, (x, 0.5, z))
    p.rotation_euler = (0, rot, 0)
    body = smooth_sphere(f"{name}_body", r=0.30, segs=20, rings=14, loc=(0, 0, 0), parent=p, mat=MAT_RAPTOR_BODY, scale=(1.8, 0.7, 0.8))
    # head_p
    head_pp = empty(f"{name}_head_p", (0.60, 0.20, 0), parent=p)
    head = smooth_sphere(f"{name}_head", r=0.20, segs=16, rings=12, loc=(0, 0, 0), parent=head_pp, mat=MAT_RAPTOR_BODY, scale=(1.5, 0.9, 0.8))
    # eyes
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        eye = smooth_sphere(f"{name}_eye_{side}", r=0.03, segs=8, rings=6, loc=(0.18, 0.08, dz), parent=head_pp, mat=MAT_TREX_EYE)
    # 2 legs
    for side, dz in [("L", 0.15), ("R", -0.15)]:
        leg = smooth_cone(f"{name}_leg_{side}", r1=0.08, r2=0.06, depth=0.5, segs=10, loc=(-0.10, -0.40, dz), parent=p, mat=MAT_RAPTOR_BODY)
    # tail
    tail = smooth_cone(f"{name}_tail", r1=0.10, r2=0.02, depth=0.8, segs=10, loc=(-0.45, 0, 0), parent=p, mat=MAT_RAPTOR_BODY)
    tail.rotation_euler = (0, math.radians(-90), 0)
    # 2 small arms
    for side, dz in [("L", 0.18), ("R", -0.18)]:
        arm = smooth_cone(f"{name}_arm_{side}", r1=0.05, r2=0.03, depth=0.25, segs=8, loc=(0.20, -0.05, dz), parent=p, mat=MAT_RAPTOR_BODY)
    return p, head_pp

raptor1_p, raptor1_head = make_raptor("raptor_1", 5, 4, math.radians(-30))
raptor2_p, raptor2_head = make_raptor("raptor_2", -5, 4, math.radians(30))

# --- volcan en éruption arrière-plan -----------------------------
volcano_p = empty("volcano", (10, 0, 8))
# cone shape
volcano_base = smooth_cone("volcano_base", r1=3.5, r2=1.0, depth=4.5, segs=20, loc=(0, 2.25, 0), parent=volcano_p, mat=MAT_VOLCANO_DARK)
volcano_base.rotation_euler = (math.radians(90), 0, 0)
# crater (top emissive lava)
crater = smooth_cone("crater", r1=0.9, r2=0.9, depth=0.10, segs=20, loc=(0, 4.50, 0), parent=volcano_p, mat=MAT_LAVA_HOT)
crater.rotation_euler = (math.radians(90), 0, 0)
# lava bulge
volcano_bulge = smooth_sphere("volcano_bulge", r=0.6, segs=18, rings=14, loc=(0, 4.6, 0), parent=volcano_p, mat=MAT_LAVA_HOT, scale=(1.0, 0.5, 1.0))
# 4 smoke puffs rising
volcano_smokes = []
for k in range(4):
    py = 5.2 + k * 0.5
    pr = 0.4 + k * 0.10
    puff = smooth_sphere(f"volcano_smoke_{k}", r=pr, segs=16, rings=12, loc=(0, py, 0), parent=volcano_p, mat=MAT_SMOKE)
    volcano_smokes.append((puff, k))
# 2 lava streams on flanks
for side, ax in [("L", math.radians(40)), ("R", math.radians(220))]:
    for j in range(5):
        t = j / 4
        h = 4.3 - t * 3.5
        r = 1.0 + t * 2.5
        sx = math.cos(ax) * r
        sz = math.sin(ax) * r
        seg = smooth_sphere(f"lava_{side}_{j}", r=0.18 - j * 0.02, segs=14, rings=10, loc=(sx, h, sz), parent=volcano_p, mat=MAT_LAVA, scale=(1.2, 0.5, 1.2))

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

# T-Rex walks in place: body bob + slight rotate Y heading + tilt
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    by = 2.5 + 0.12 * math.sin(tt * math.pi * 8.0)  # walking bob
    rotY = math.radians(15) * math.sin(tt * math.pi * 2.0)  # looking around
    tilt = math.radians(3) * math.cos(tt * math.pi * 4.0)
    kf_loc(trex, f, (0, by, 0))
    kf_rot(trex, f, (0, rotY, tilt))

# head tilts looking left/right + bob
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    head_y = math.radians(-10) + math.radians(15) * math.sin(tt * math.pi * 3.0)
    head_x = math.radians(8) * math.cos(tt * math.pi * 4.0)
    kf_rot(head_p, f, (head_x, 0, head_y))

# jaw opens and closes cyclically (roar)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    # 2 cycles of roar
    angle = math.radians(25) * max(0, math.sin(tt * math.pi * 4.0))
    kf_rot(jaw_p, f, (0, 0, -angle))

# 2 eyes pulse red intense
for eye in trex_eyes:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 7.0)
        kf_scale(eye, f, (s, s, s))

# 2 legs alternate (walking cycle)
for i, leg_p in enumerate(legs):
    sign = 1 if i == 0 else -1
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # walking : forward swing then back swing
        angle = math.radians(20) * math.sin(tt * math.pi * 8.0 + (math.pi if i == 1 else 0))
        kf_rot(leg_p, f, (0, 0, angle))

# 2 arms wiggle subtle
for i, arm_p in enumerate(arms):
    base_rot = arm_p.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        wiggle = math.radians(15) * math.sin(tt * math.pi * 6.0 + i * 0.5)
        kf_rot(arm_p, f, (0, 0, base_rot[2] + wiggle))

# tail swish (wave-like, each segment offset)
for j, seg_p in enumerate(tail_segments):
    phase = j * 0.6
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # propagated wave
        wave = math.radians(15) * math.sin(tt * math.pi * 4.0 - phase)
        kf_rot(seg_p, f, (0, wave, 0))

# 3 fougères sway
for i, fp in enumerate(ferns):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(10) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(fp, f, (bend, 0, bend * 0.5))

# 2 raptors head bob + drift
for i, (rp, rhead) in enumerate([(raptor1_p, raptor1_head), (raptor2_p, raptor2_head)]):
    base = (rp.location.x, rp.location.y, rp.location.z)
    phase = i * 0.7
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dx = base[0] + 0.4 * math.sin(tt * math.pi * 2.0 + phase)
        dz = base[2] + 0.3 * math.cos(tt * math.pi * 2.0 + phase)
        kf_loc(rp, f, (dx, base[1], dz))
        bob = math.radians(8) * math.sin(tt * math.pi * 5.0 + phase)
        kf_rot(rhead, f, (bob, 0, 0))

# volcano bulge pulse + smoke rise
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.20 * math.sin(tt * math.pi * 6.0)
    kf_scale(volcano_bulge, f, (s, 0.5 * s, s))

for puff, k in volcano_smokes:
    phase = k * 8
    base_y = 5.2 + k * 0.5
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 70
        lt = local_f / 70
        dy = base_y + lt * 2.5
        dx = math.sin(lt * math.pi * 3.0) * 0.25
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.6 + lt * 1.6
        kf_scale(puff, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_trex] wrote {OUT}")
