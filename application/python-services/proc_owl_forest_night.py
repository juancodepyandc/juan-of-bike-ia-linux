"""
proc_owl_forest_night.py — 153e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Chouette nocturne sur branche dans forêt :
- corps oiseau bevelé smooth (sphère étirée)
- 2 yeux énormes émissifs jaunes + 2 pupilles noires
- bec courbé doré
- 2 ailes membraneuses repliées avec 5 plumes chacune
- 24 plumes corps détaillées en patches
- 2 serres griffues
- branche arbre support
- 3 arbres background
- lune émissive + halo
- 40 étoiles
- 8 lucioles spirales émissives
- 3 brouillard puffs
- ciel nuit forêt

Animations multi-axes simultanées :
- tête tourne 180° lentement (signature owl)
- 2 yeux pulse intense
- body breathe
- 8 lucioles spirales 3D différentielles
- lune halo breathe
- 40 étoiles scintillent
- 3 brouillard drift

Sortie : output/3d/pbr_owl_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_owl_proc.glb"))

random.seed(0xCAFF33)

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
MAT_SKY_NIGHT = make_mat("sky_night", (0.04, 0.05, 0.12), roughness=1.0, emi=(0.05, 0.06, 0.15), emi_strength=0.5)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.5)
MAT_MOON = make_mat("moon", (0.95, 0.92, 0.85), roughness=0.0, emi=(0.95, 0.92, 0.85), emi_strength=7.0)
MAT_MOON_HALO = make_mat("moon_halo", (0.92, 0.92, 0.85), roughness=0.0, alpha=0.25, emi=(0.92, 0.90, 0.80), emi_strength=2.8)
MAT_OWL_BROWN = make_mat("owl_brown", (0.55, 0.35, 0.20), roughness=0.6, emi=(0.18, 0.10, 0.05), emi_strength=0.2)
MAT_OWL_DARK = make_mat("owl_dark", (0.25, 0.15, 0.08), roughness=0.7)
MAT_OWL_LIGHT = make_mat("owl_light", (0.85, 0.70, 0.45), roughness=0.5, emi=(0.30, 0.20, 0.10), emi_strength=0.25)
MAT_OWL_CHEST = make_mat("owl_chest", (0.95, 0.92, 0.85), roughness=0.5, emi=(0.35, 0.32, 0.25), emi_strength=0.25)
MAT_EYE_YELLOW = make_mat("eye_yellow", (1.0, 0.95, 0.30), roughness=0.0, emi=(1.0, 0.95, 0.30), emi_strength=14.0)
MAT_PUPIL = make_mat("pupil", (0.05, 0.05, 0.05), roughness=0.0)
MAT_BEAK_GOLD = make_mat("beak_gold", (0.85, 0.65, 0.20), metallic=0.5, roughness=0.30, emi=(0.30, 0.20, 0.08), emi_strength=0.4)
MAT_CLAW = make_mat("claw", (0.20, 0.15, 0.10), metallic=0.5, roughness=0.40)
MAT_BRANCH = make_mat("branch", (0.25, 0.18, 0.10), roughness=0.95)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.20, 0.12, 0.08), roughness=0.95)
MAT_TREE_LEAVES = make_mat("tree_leaves", (0.10, 0.20, 0.10), roughness=0.85, emi=(0.04, 0.10, 0.04), emi_strength=0.2)
MAT_FIREFLY = make_mat("firefly", (1.0, 0.95, 0.40), roughness=0.0, emi=(1.0, 0.95, 0.40), emi_strength=10.0)
MAT_FIREFLY_GREEN = make_mat("firefly_g", (0.40, 1.0, 0.50), roughness=0.0, emi=(0.40, 1.0, 0.50), emi_strength=9.0)
MAT_MIST = make_mat("mist", (0.55, 0.60, 0.70), roughness=1.0, alpha=0.35, emi=(0.40, 0.45, 0.55), emi_strength=1.0)
MAT_GROUND = make_mat("ground", (0.10, 0.10, 0.08), roughness=0.95)

# --- backdrop : night sky -----------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 6), mat=MAT_SKY_NIGHT)

# 40 stars
for i in range(40):
    x = random.uniform(-15, 15)
    z = random.uniform(8, 14)
    y = random.uniform(15, 16)
    r = random.uniform(0.06, 0.11)
    s = smooth_sphere(f"star_{i}", r=r, segs=10, rings=8, loc=(x, y, z), mat=MAT_STAR)
    s["_phase"] = (i * 11) % 47

# moon + halo
moon_p = empty("moon_p", (-7, 13, 9))
moon = smooth_sphere("moon", r=1.0, segs=24, rings=18, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON)
moon_halo = smooth_sphere("moon_halo", r=2.0, segs=22, rings=14, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)

# ground
ground = beveled_cube("ground", (30, 0.1, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND)

# 3 background trees
for i, (tx, tz) in enumerate([(-9, 6), (9, 6), (0, 8)]):
    tp = empty(f"tree_{i}", (tx, 0, tz))
    trunk = smooth_cone(f"tree_{i}_trunk", r1=0.30, r2=0.20, depth=4.0, segs=12, loc=(0, 2.0, 0), parent=tp, mat=MAT_TREE_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # foliage
    for j in range(7):
        ja = j * (math.pi * 2 / 7)
        f_obj = smooth_sphere(f"tree_{i}_f_{j}", r=0.9, segs=18, rings=12, loc=(math.cos(ja) * 0.6, 4.5 + random.uniform(-0.2, 0.4), math.sin(ja) * 0.6), parent=tp, mat=MAT_TREE_LEAVES, scale=(1.3, 1.0, 1.3))

# main branch (where owl sits)
branch_p = empty("branch_p", (0, 3.0, 0))
# main horizontal branch
main_branch = smooth_cone("main_branch", r1=0.20, r2=0.15, depth=3.5, segs=14, loc=(0, 0, 0), parent=branch_p, mat=MAT_BRANCH)
main_branch.rotation_euler = (0, math.radians(90), 0)
# branch attached to background tree
attach = smooth_cone("branch_attach", r1=0.25, r2=0.20, depth=1.0, segs=12, loc=(1.8, 0.3, 0), parent=branch_p, mat=MAT_BRANCH)
attach.rotation_euler = (0, 0, math.radians(45))
# 3 small twigs
for k in range(3):
    a = -1.0 + k * 1.0
    twig = smooth_cone(f"twig_{k}", r1=0.04, r2=0.02, depth=0.40, segs=8, loc=(a, 0.10, 0), parent=branch_p, mat=MAT_BRANCH)
    twig.rotation_euler = (math.radians(60), 0, math.radians(random.uniform(-30, 30)))

# --- CHOUETTE / OWL ----------------------------------------
owl = empty("owl", (0, 3.30, 0))

# Body (sphere bulbous)
def make_body(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=0.55)
    bmesh.ops.scale(bm, vec=(1.0, 1.4, 0.85), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0, 0)
    me.materials.append(MAT_OWL_BROWN)
    smooth_shade(me)
    return o

body = make_body("owl_body", owl)

# Chest plate (lighter front)
chest = smooth_sphere("owl_chest", r=0.40, segs=24, rings=18, loc=(0, 0.10, 0.30), parent=owl, mat=MAT_OWL_CHEST, scale=(1.0, 1.3, 0.4))

# 24 plumes patches (small darker spheres on body)
for i in range(24):
    a = i * (math.pi * 2 / 12) + (i // 12) * 0.2
    ring = i // 12
    py = 0.40 - ring * 0.30
    pr = 0.55 if ring == 0 else 0.50
    px = math.cos(a) * pr * 0.9
    pz = math.sin(a) * pr * 0.5
    feather = smooth_sphere(f"feather_{i}", r=0.08, segs=10, rings=8, loc=(px, py, pz), parent=owl, mat=MAT_OWL_DARK, scale=(1.0, 0.4, 1.0))

# Head (large round, articulated for 180° turn)
head_p = empty("owl_head_p", (0, 0.90, 0), parent=owl)
head = smooth_sphere("owl_head", r=0.45, segs=28, rings=20, loc=(0, 0, 0), parent=head_p, mat=MAT_OWL_BROWN, scale=(1.1, 0.95, 1.0))

# 2 yeux énormes (HUGE for owl)
owl_eyes = []
owl_pupils = []
for side, dz in [("L", 0.18), ("R", -0.18)]:
    eye_socket = smooth_sphere(f"eye_socket_{side}", r=0.20, segs=20, rings=14, loc=(0.20, 0.05, dz), parent=head_p, mat=MAT_OWL_LIGHT, scale=(1.0, 1.0, 0.6))
    eye = smooth_sphere(f"eye_{side}", r=0.17, segs=18, rings=14, loc=(0.30, 0.05, dz), parent=head_p, mat=MAT_EYE_YELLOW)
    owl_eyes.append(eye)
    pupil = smooth_sphere(f"pupil_{side}", r=0.06, segs=14, rings=10, loc=(0.42, 0.05, dz), parent=head_p, mat=MAT_PUPIL)
    owl_pupils.append(pupil)

# Beak gold curved
beak = smooth_cone("beak", r1=0.08, r2=0.02, depth=0.18, segs=12, loc=(0.40, -0.15, 0), parent=head_p, mat=MAT_BEAK_GOLD)
beak.rotation_euler = (0, math.radians(90), 0)

# 2 ear tufts (small feather tufts on top of head)
for side, dz in [("L", 0.20), ("R", -0.20)]:
    tuft = smooth_cone(f"ear_tuft_{side}", r1=0.06, r2=0.0, depth=0.25, segs=8, loc=(-0.10, 0.40, dz), parent=head_p, mat=MAT_OWL_DARK)
    tuft.rotation_euler = (math.radians(-10), 0, math.radians(15 if side == "L" else -15))

# --- 2 ailes repliées ---
for side, dz, sign in [("L", 0.50, 1), ("R", -0.50, -1)]:
    wing_p = empty(f"wing_p_{side}", (0, 0.10, dz), parent=owl)
    wing_p.rotation_euler = (0, 0, math.radians(15 * sign))
    # main wing body (folded)
    wing_body = smooth_sphere(f"wing_body_{side}", r=0.30, segs=20, rings=14, loc=(0, -0.20, 0), parent=wing_p, mat=MAT_OWL_BROWN, scale=(0.55, 1.5, 0.4))
    # 5 visible feathers cascading
    for k in range(5):
        kz = -0.10 + k * 0.04
        ky = -0.40 - k * 0.05
        feather = smooth_cone(f"wing_feather_{side}_{k}", r1=0.05, r2=0.02, depth=0.30, segs=8, loc=(0, ky, kz), parent=wing_p, mat=MAT_OWL_DARK)
        feather.rotation_euler = (math.radians(180), 0, 0)

# --- 2 pattes/serres griffues ---
for side, dz in [("L", 0.15), ("R", -0.15)]:
    leg_p = empty(f"leg_p_{side}", (0, -0.60, dz), parent=owl)
    # leg (yellow)
    leg = smooth_cone(f"leg_{side}", r1=0.05, r2=0.05, depth=0.15, segs=10, loc=(0, -0.08, 0), parent=leg_p, mat=MAT_BEAK_GOLD)
    leg.rotation_euler = (math.radians(90), 0, 0)
    # 3 claws per foot (radial)
    for k in range(3):
        ka = -0.25 + k * 0.25
        claw = smooth_cone(f"claw_{side}_{k}", r1=0.025, r2=0.0, depth=0.10, segs=6, loc=(math.cos(ka) * 0.08, -0.20, math.sin(ka) * 0.08), parent=leg_p, mat=MAT_CLAW)
        claw.rotation_euler = (math.radians(150), 0, ka)

# --- 8 lucioles spiraling around owl ---
fireflies = []
for i in range(8):
    a0 = i * (math.pi * 2 / 8)
    py = 3.0 + random.uniform(-0.5, 0.5)
    px = math.cos(a0) * 1.5
    pz = math.sin(a0) * 1.5
    mat = MAT_FIREFLY if i % 3 != 0 else MAT_FIREFLY_GREEN
    fr = smooth_sphere(f"firefly_{i}", r=random.uniform(0.06, 0.10), segs=10, rings=8, loc=(px, py, pz), mat=mat)
    fireflies.append((fr, a0, random.uniform(0.7, 1.3), random.uniform(0, 1)))

# --- 3 mist puffs au sol ---
mist_objs = []
for i, (mx, mz) in enumerate([(-4, 2), (4, 2), (0, -3)]):
    m = smooth_sphere(f"mist_{i}", r=1.2, segs=18, rings=12, loc=(mx, 0.4, mz), mat=MAT_MIST, scale=(1.5, 0.4, 1.2))
    mist_objs.append((m, mx, mz, random.uniform(0, math.pi * 2)))

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

# Head turns 180° back and forth (signature owl)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    # cycle : straight → left 90 → right 90 → straight
    angle = math.radians(90) * math.sin(tt * math.pi * 2.0)
    kf_rot(head_p, f, (0, angle, 0))

# 2 eyes pulse intense
for eye in owl_eyes:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 6.0)
        kf_scale(eye, f, (s, s, s))

# 2 pupils dilate (subtle scale)
for pupil in owl_pupils:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 3.0)
        kf_scale(pupil, f, (s, s, s))

# Body subtle breathe + occasional puff (fluffy)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.04 * math.sin(tt * math.pi * 4.0)
    kf_scale(body, f, (s, 1.0, s))

# 40 stars twinkle
for i in range(40):
    star = bpy.data.objects.get(f"star_{i}")
    if not star:
        continue
    phase = star["_phase"]
    for f in range(1, FRAMES + 1, 6):
        tt = (f - 1) / (FRAMES - 1)
        local = (math.sin(tt * math.pi * 6.0 + phase * 0.13) + 1) * 0.5
        s = 0.7 + 0.5 * local
        kf_scale(star, f, (s, s, s))

# Moon halo breathe
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.12 * math.sin(tt * math.pi * 3.0)
    kf_scale(moon_halo, f, (s, s, s))

# 8 fireflies spiral 3D
for fr, a0, spd, ph in fireflies:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 4.0 * spd
        r = 1.5 + 0.4 * math.sin(tt * math.pi * 3.0 + a0)
        dx = math.cos(angle) * r
        dz = math.sin(angle) * r
        dy = 3.0 + math.sin(tt * math.pi * 3.0 + a0 + ph) * 1.2
        kf_loc(fr, f, (dx, dy, dz))
        s = 0.8 + 0.5 * math.sin(tt * math.pi * 6.0 + a0 + ph)
        kf_scale(fr, f, (s, s, s))

# 3 mist drift
for m, mx, mz, ph in mist_objs:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        dx = mx + 0.5 * math.sin(tt * math.pi * 1.5 + ph)
        dz = mz + 0.4 * math.cos(tt * math.pi * 1.2 + ph)
        kf_loc(m, f, (dx, 0.4, dz))
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 3.0 + ph)
        kf_scale(m, f, (1.5 * s, 0.4, 1.2 * s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_owl] wrote {OUT}")
