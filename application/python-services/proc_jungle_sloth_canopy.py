"""
proc_jungle_sloth_canopy.py — 185e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie).

Canopée jungle avec paresseux :
- grand arbre tropical massif central
- 3 paresseux articulés accrochés aux branches
- 8 toucans aux becs colorés
- 12 lianes
- 30 feuilles tropicales géantes
- 6 fleurs exotiques émissives
- papillons jungle
- 4 grenouilles colorées
- ciel humide + brouillard tropical
- cascade arrière
- 4 singes branches

Animations multi-axes simultanées :
- 3 paresseux mouvement très lent
- toucans bec ouvre/ferme
- 8 papillons flap + orbit
- 4 grenouilles bondissent
- lianes ondulent
- cascade flow
- 4 singes swing branches

Sortie : output/3d/pbr_jungle_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_jungle_proc.glb"))

random.seed(0x171064)


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
MAT_SKY = make_mat("sky_jungle", (0.35, 0.55, 0.55), roughness=1.0, emi=(0.20, 0.35, 0.30), emi_strength=0.8)
MAT_GROUND = make_mat("jungle_ground", (0.20, 0.30, 0.15), roughness=0.85, emi=(0.05, 0.15, 0.05), emi_strength=0.3)
MAT_TRUNK = make_mat("trunk", (0.30, 0.18, 0.10), roughness=0.85)
MAT_BARK = make_mat("bark", (0.45, 0.30, 0.18), roughness=0.85)
MAT_LEAF = make_mat("leaf", (0.20, 0.55, 0.20), roughness=0.6, emi=(0.08, 0.25, 0.08), emi_strength=0.4)
MAT_LEAF_BRIGHT = make_mat("leaf_bright", (0.30, 0.75, 0.30), roughness=0.55, emi=(0.15, 0.40, 0.15), emi_strength=0.5)
MAT_LIANA = make_mat("liana", (0.30, 0.45, 0.15), roughness=0.7)
MAT_SLOTH = make_mat("sloth", (0.55, 0.45, 0.30), roughness=0.7, emi=(0.20, 0.18, 0.12), emi_strength=0.3)
MAT_SLOTH_FACE = make_mat("sloth_face", (0.75, 0.65, 0.45), roughness=0.65, emi=(0.30, 0.25, 0.18), emi_strength=0.4)
MAT_SLOTH_EYE = make_mat("sloth_eye", (0.10, 0.05, 0.05), roughness=0.0)
MAT_SLOTH_CLAW = make_mat("sloth_claw", (0.40, 0.30, 0.18), metallic=0.4, roughness=0.30)
MAT_TOUCAN_BODY = make_mat("toucan_body", (0.10, 0.10, 0.10), roughness=0.5)
MAT_TOUCAN_BELLY = make_mat("toucan_belly", (0.95, 0.95, 0.90), roughness=0.5, emi=(0.40, 0.40, 0.38), emi_strength=0.3)
MAT_TOUCAN_BEAK_A = make_mat("toucan_beak_A", (0.95, 0.55, 0.10), roughness=0.4, emi=(0.45, 0.25, 0.05), emi_strength=0.5)
MAT_TOUCAN_BEAK_B = make_mat("toucan_beak_B", (0.95, 0.85, 0.20), roughness=0.4, emi=(0.45, 0.40, 0.10), emi_strength=0.5)
MAT_TOUCAN_BEAK_C = make_mat("toucan_beak_C", (0.95, 0.20, 0.30), roughness=0.4, emi=(0.45, 0.05, 0.10), emi_strength=0.5)
MAT_TOUCAN_EYE = make_mat("toucan_eye", (0.95, 0.85, 0.20), roughness=0.0, emi=(0.95, 0.85, 0.20), emi_strength=10.0)
MAT_FLOWER_R = make_mat("flower_red", (0.95, 0.25, 0.30), roughness=0.4, emi=(0.55, 0.10, 0.15), emi_strength=0.8)
MAT_FLOWER_P = make_mat("flower_pink", (0.95, 0.55, 0.85), roughness=0.4, emi=(0.55, 0.30, 0.45), emi_strength=0.8)
MAT_FLOWER_O = make_mat("flower_orange", (1.0, 0.55, 0.10), roughness=0.4, emi=(0.50, 0.25, 0.05), emi_strength=0.8)
MAT_BUTTERFLY_A = make_mat("butterfly_A", (0.95, 0.30, 0.85), roughness=0.3, alpha=0.85, emi=(0.50, 0.10, 0.45), emi_strength=1.5)
MAT_BUTTERFLY_B = make_mat("butterfly_B", (0.30, 0.95, 0.55), roughness=0.3, alpha=0.85, emi=(0.10, 0.50, 0.25), emi_strength=1.5)
MAT_FROG_GREEN = make_mat("frog_green", (0.30, 0.85, 0.30), roughness=0.5, emi=(0.10, 0.40, 0.10), emi_strength=0.6)
MAT_FROG_RED = make_mat("frog_red", (0.95, 0.30, 0.20), roughness=0.5, emi=(0.45, 0.10, 0.05), emi_strength=0.7)
MAT_FROG_BLUE = make_mat("frog_blue", (0.30, 0.55, 0.95), roughness=0.5, emi=(0.10, 0.25, 0.45), emi_strength=0.7)
MAT_MONKEY = make_mat("monkey", (0.30, 0.18, 0.12), roughness=0.7)
MAT_MONKEY_FACE = make_mat("monkey_face", (0.85, 0.65, 0.45), roughness=0.6, emi=(0.30, 0.22, 0.15), emi_strength=0.4)
MAT_WATER = make_mat("water", (0.30, 0.70, 0.85), roughness=0.10, alpha=0.75, emi=(0.20, 0.50, 0.65), emi_strength=2.0)
MAT_FOG = make_mat("fog", (0.65, 0.80, 0.75), roughness=1.0, alpha=0.35, emi=(0.40, 0.55, 0.45), emi_strength=0.6)
MAT_ROCK = make_mat("rock", (0.30, 0.30, 0.25), roughness=0.95)


# --- backdrop : jungle sky + ground -------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, 13, 10), mat=MAT_SKY)
ground = beveled_cube("ground", (30, 0.2, 20), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND)

# 8 fog puffs tropical
fog_puffs = []
for fk in range(8):
    fx = random.uniform(-12, 12)
    fz = random.uniform(-3, 7)
    fy = random.uniform(1, 4)
    fp = smooth_sphere(f"fog_{fk}", r=random.uniform(0.8, 1.4), segs=14, rings=8, loc=(fx, fy, fz), mat=MAT_FOG, scale=(1.0, 0.25, 1.0))
    fp["_base_x"] = fx
    fp["_phase"] = fk * 0.30
    fog_puffs.append(fp)


# --- GRAND ARBRE TROPICAL central ---------------------------------------
tree_p = empty("tree_main", (0, 0, 0))
# Trunk huge
TRUNK_HEIGHT = 6.5
trunk = smooth_cone("trunk_main", r1=0.85, r2=0.55, depth=TRUNK_HEIGHT, segs=18, loc=(0, TRUNK_HEIGHT / 2, 0), parent=tree_p, mat=MAT_TRUNK)
# bark texture details (8 spots)
for bk in range(8):
    ba = bk * (math.pi * 2 / 8)
    by_off = random.uniform(1, 5)
    smooth_sphere(f"bark_{bk}", r=0.10, segs=10, rings=8, loc=(math.cos(ba) * 0.7, by_off, math.sin(ba) * 0.7), parent=tree_p, mat=MAT_BARK, scale=(0.6, 1.5, 0.6))

# 6 grosses branches main
main_branches = []
BRANCH_CONFIGS = [
    (math.radians(0), 4.5, 45),
    (math.radians(60), 5.0, 30),
    (math.radians(120), 4.5, 40),
    (math.radians(180), 5.5, 35),
    (math.radians(240), 5.0, 25),
    (math.radians(300), 4.7, 50),
]
for bi, (ba, by, pitch) in enumerate(BRANCH_CONFIGS):
    branch_p = empty(f"branch_{bi}_p", (math.cos(ba) * 0.30, by, math.sin(ba) * 0.30), parent=tree_p)
    branch_p.rotation_euler = (0, -ba, math.radians(pitch))
    main_branches.append(branch_p)
    # main branch
    smooth_cone(f"branch_{bi}_main", r1=0.25, r2=0.10, depth=3.5, segs=12, loc=(0, 0, 1.75), parent=branch_p, mat=MAT_TRUNK)
    bp_obj = bpy.data.objects.get(f"branch_{bi}_main")
    if bp_obj:
        bp_obj.rotation_euler = (math.radians(90), 0, 0)
    # 5 leaf clusters along branch
    for lk in range(5):
        lz = 0.8 + lk * 0.55
        ll_x = random.uniform(-0.3, 0.3)
        ll_y = random.uniform(-0.2, 0.2)
        lmat = MAT_LEAF if lk % 2 == 0 else MAT_LEAF_BRIGHT
        smooth_sphere(f"branch_{bi}_lf_{lk}", r=random.uniform(0.35, 0.55), segs=14, rings=10, loc=(ll_x, ll_y, lz), parent=branch_p, mat=lmat, scale=(1.0, 0.45, 1.0))

# Top crown leaves (dense)
for cr in range(15):
    ca = cr * (math.pi * 2 / 15) + random.uniform(-0.2, 0.2)
    cr_r = random.uniform(0.6, 1.4)
    cx = math.cos(ca) * cr_r
    cz = math.sin(ca) * cr_r
    cy = TRUNK_HEIGHT + random.uniform(-0.3, 0.6)
    smooth_sphere(f"crown_{cr}", r=random.uniform(0.50, 0.85), segs=14, rings=10, loc=(cx, cy, cz), parent=tree_p, mat=MAT_LEAF_BRIGHT, scale=(1.0, 0.55, 1.0))


# --- 3 PARESSEUX accrochés aux branches -----------------------------
sloths = []
SLOTH_BRANCHES = [0, 2, 4]
for si, bi in enumerate(SLOTH_BRANCHES):
    parent_b = main_branches[bi]
    sloth_p = empty(f"sloth_{si}_p", (0, 0, 2.0), parent=parent_b)
    sloth_p.rotation_euler = (0, 0, math.radians(-90))  # hanging upside down
    sloths.append({"p": sloth_p, "phase": si * 1.0})
    # body
    smooth_sphere(f"sloth_{si}_body", r=0.30, segs=18, rings=14, loc=(0, 0, 0), parent=sloth_p, mat=MAT_SLOTH, scale=(1.4, 0.95, 1.0))
    # head
    smooth_sphere(f"sloth_{si}_head", r=0.18, segs=16, rings=12, loc=(0.35, 0, 0), parent=sloth_p, mat=MAT_SLOTH_FACE)
    # 2 eyes
    for ek, ez in [("L", 0.06), ("R", -0.06)]:
        smooth_sphere(f"sloth_{si}_eye_{ek}", r=0.025, segs=10, rings=6, loc=(0.45, 0.05, ez), parent=sloth_p, mat=MAT_SLOTH_EYE)
    # nose
    smooth_sphere(f"sloth_{si}_nose", r=0.04, segs=10, rings=6, loc=(0.50, 0, 0), parent=sloth_p, mat=MAT_SLOTH_EYE)
    # 4 PATTES longues griffues (hanging)
    for lk, (lx, lz) in enumerate([(-0.20, 0.18), (-0.20, -0.18), (0.20, 0.18), (0.20, -0.18)]):
        leg_p = empty(f"sloth_{si}_leg_p_{lk}", (lx, -0.15, lz), parent=sloth_p)
        leg_p.rotation_euler = (0, 0, math.radians(90))  # legs reach up to grip branch
        smooth_cone(f"sloth_{si}_leg_{lk}", r1=0.10, r2=0.08, depth=0.45, segs=8, loc=(0, 0.22, 0), parent=leg_p, mat=MAT_SLOTH)
        # 3 long claws at end
        for ck in range(3):
            ca = (ck - 1) * 0.15
            smooth_cone(f"sloth_{si}_claw_{lk}_{ck}", r1=0.025, r2=0.0, depth=0.15, segs=4, loc=(ca, 0.50, 0), parent=leg_p, mat=MAT_SLOTH_CLAW)
            cw = bpy.data.objects.get(f"sloth_{si}_claw_{lk}_{ck}")
            if cw:
                cw.rotation_euler = (math.radians(-30), 0, 0)


# --- 8 TOUCANS aux becs colorés -----------------------------------
toucans = []
BEAK_MATS = [MAT_TOUCAN_BEAK_A, MAT_TOUCAN_BEAK_B, MAT_TOUCAN_BEAK_C]
for ti in range(8):
    # perch on different branches
    bi = ti % 6
    parent_b = main_branches[bi]
    ti_off = (ti // 6) * 0.8
    tp = empty(f"toucan_{ti}_p", (-0.5 + ti_off, 0, 1.5 + ti * 0.20), parent=parent_b)
    toucans.append({"p": tp, "phase": ti * 0.30})
    # body
    smooth_sphere(f"toucan_{ti}_body", r=0.15, segs=14, rings=10, loc=(0, 0, 0), parent=tp, mat=MAT_TOUCAN_BODY, scale=(1.0, 1.3, 0.85))
    # belly
    smooth_sphere(f"toucan_{ti}_belly", r=0.10, segs=12, rings=8, loc=(0, -0.05, 0.10), parent=tp, mat=MAT_TOUCAN_BELLY, scale=(1.0, 1.0, 0.45))
    # head
    smooth_sphere(f"toucan_{ti}_head", r=0.10, segs=14, rings=10, loc=(0, 0.18, 0.05), parent=tp, mat=MAT_TOUCAN_BODY)
    # BEAK COLORÉ huge (signature toucan)
    beak_p = empty(f"toucan_{ti}_beak_p", (0, 0.20, 0.15), parent=tp)
    bmat = BEAK_MATS[ti % 3]
    smooth_cone(f"toucan_{ti}_beak", r1=0.10, r2=0.0, depth=0.35, segs=10, loc=(0, 0, 0.15), parent=beak_p, mat=bmat)
    bk_obj = bpy.data.objects.get(f"toucan_{ti}_beak")
    if bk_obj:
        bk_obj.rotation_euler = (math.radians(90), 0, 0)
    # eye
    smooth_sphere(f"toucan_{ti}_eye", r=0.025, segs=10, rings=6, loc=(0.05, 0.20, 0.10), parent=tp, mat=MAT_TOUCAN_EYE)
    # 2 wings small
    for wk, wz in [(0, 0.08), (1, -0.08)]:
        smooth_sphere(f"toucan_{ti}_w_{wk}", r=0.08, segs=10, rings=6, loc=(0, 0, wz), parent=tp, mat=MAT_TOUCAN_BODY, scale=(0.4, 1.2, 0.5))
    toucans[ti]["beak"] = beak_p


# --- 12 LIANES pendantes ------------------------------------------
lianas = []
for li in range(12):
    a = li * (math.pi * 2 / 12) + random.uniform(-0.1, 0.1)
    lr = random.uniform(2.5, 4.5)
    lx = math.cos(a) * lr
    lz = math.sin(a) * lr * 0.7
    lp = empty(f"liana_{li}_p", (lx, TRUNK_HEIGHT - 0.5, lz))
    lianas.append({"p": lp, "phase": li * 0.20})
    # 5 segments forming hanging liana
    cur = lp
    for sg in range(5):
        e = empty(f"liana_{li}_seg_p_{sg}", (0, -0.50, 0), parent=cur)
        smooth_cone(f"liana_{li}_seg_{sg}", r1=0.04, r2=0.03, depth=0.50, segs=6, loc=(0, -0.25, 0), parent=e, mat=MAT_LIANA)
        # 2 leaves on each segment
        for lk in range(2):
            smooth_sphere(f"liana_{li}_lf_{sg}_{lk}", r=0.10, segs=10, rings=6, loc=(0.15 if lk == 0 else -0.15, -0.25, 0), parent=e, mat=MAT_LEAF, scale=(0.9, 0.10, 1.4))
        cur = e


# --- 6 FLEURS EXOTIQUES émissives -------------------------------
flowers = []
FLOWER_MATS = [MAT_FLOWER_R, MAT_FLOWER_P, MAT_FLOWER_O]
for fk in range(6):
    a = fk * (math.pi * 2 / 6) + 0.3
    r = random.uniform(3, 6)
    fx = math.cos(a) * r
    fz = math.sin(a) * r * 0.6
    fp = empty(f"flower_{fk}_p", (fx, 0, fz))
    flowers.append({"p": fp, "phase": fk * 0.30})
    # stem
    smooth_cone(f"flower_{fk}_stem", r1=0.03, r2=0.025, depth=1.2, segs=6, loc=(0, 0.6, 0), parent=fp, mat=MAT_LIANA)
    # 2 leaves on stem
    for lk in range(2):
        smooth_sphere(f"flower_{fk}_lf_{lk}", r=0.15, segs=12, rings=8, loc=(0.15 if lk == 0 else -0.15, 0.7 + lk * 0.10, 0), parent=fp, mat=MAT_LEAF, scale=(1.5, 0.10, 0.85))
    # 5 PÉTALES émissifs
    fmat = FLOWER_MATS[fk % 3]
    for pk in range(5):
        pa = pk * (math.pi * 2 / 5)
        smooth_cone(f"flower_{fk}_pet_{pk}", r1=0.08, r2=0.0, depth=0.18, segs=6, loc=(math.cos(pa) * 0.10, 1.25, math.sin(pa) * 0.10), parent=fp, mat=fmat)
    # center
    smooth_sphere(f"flower_{fk}_ctr", r=0.06, segs=12, rings=8, loc=(0, 1.25, 0), parent=fp, mat=MAT_TOUCAN_BEAK_B)


# --- 8 PAPILLONS jungle volants ----------------------------------
butterflies = []
for bk in range(8):
    a = bk * (math.pi * 2 / 8) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 7)
    by = random.uniform(3, 8)
    bp = empty(f"butterfly_{bk}_p", (math.cos(a) * r, by, math.sin(a) * r))
    butterflies.append({"p": bp, "a": a, "r": r, "by": by, "phase": bk * 0.35})
    bmat = MAT_BUTTERFLY_A if bk % 2 == 0 else MAT_BUTTERFLY_B
    # body small
    smooth_cone(f"butterfly_{bk}_body", r1=0.03, r2=0.03, depth=0.10, segs=4, loc=(0, 0, 0), parent=bp, mat=MAT_TOUCAN_BODY)
    # 2 wings
    wL = empty(f"butterfly_{bk}_wL", (0, 0, 0.02), parent=bp)
    wR = empty(f"butterfly_{bk}_wR", (0, 0, -0.02), parent=bp)
    smooth_sphere(f"butterfly_{bk}_wL_b", r=0.18, segs=12, rings=8, loc=(0, 0, 0.10), parent=wL, mat=bmat, scale=(1.5, 0.05, 1.2))
    smooth_sphere(f"butterfly_{bk}_wR_b", r=0.18, segs=12, rings=8, loc=(0, 0, -0.10), parent=wR, mat=bmat, scale=(1.5, 0.05, 1.2))
    butterflies[bk]["wL"] = wL
    butterflies[bk]["wR"] = wR


# --- 4 GRENOUILLES colorées (jumping) -----------------------------
frogs = []
FROG_MATS = [MAT_FROG_GREEN, MAT_FROG_RED, MAT_FROG_BLUE, MAT_FROG_GREEN]
FROG_POSITIONS = [(-3, 0, 5), (3, 0, 5), (-4, 0, -1), (4, 0, -1)]
for fi, (fx, fy, fz) in enumerate(FROG_POSITIONS):
    fp = empty(f"frog_{fi}_p", (fx, fy + 0.10, fz))
    frogs.append({"p": fp, "phase": fi * 0.50, "base": (fx, fy + 0.10, fz)})
    fmat = FROG_MATS[fi]
    # body
    smooth_sphere(f"frog_{fi}_body", r=0.18, segs=18, rings=14, loc=(0, 0, 0), parent=fp, mat=fmat, scale=(1.2, 0.85, 1.0))
    # head bulge
    smooth_sphere(f"frog_{fi}_head", r=0.13, segs=14, rings=10, loc=(0.10, 0.05, 0), parent=fp, mat=fmat)
    # 2 eyes huge bulging
    for ek, ez in [("L", 0.10), ("R", -0.10)]:
        smooth_sphere(f"frog_{fi}_eye_{ek}", r=0.06, segs=12, rings=8, loc=(0.10, 0.15, ez), parent=fp, mat=MAT_TOUCAN_EYE)
        smooth_sphere(f"frog_{fi}_pupil_{ek}", r=0.03, segs=10, rings=6, loc=(0.13, 0.15, ez), parent=fp, mat=MAT_SLOTH_EYE)
    # 4 legs
    for lk, (lx, lz) in enumerate([(-0.10, 0.12), (0.10, 0.12), (-0.10, -0.12), (0.10, -0.12)]):
        smooth_sphere(f"frog_{fi}_leg_{lk}", r=0.06, segs=10, rings=6, loc=(lx, -0.08, lz), parent=fp, mat=fmat, scale=(1.0, 0.85, 1.0))


# --- 4 SINGES sur branches ----------------------------------------
monkeys = []
for mk in range(4):
    parent_b = main_branches[(mk * 2) % 6]
    mp = empty(f"monkey_{mk}_p", (0, 0, 2.5 + mk * 0.30), parent=parent_b)
    monkeys.append({"p": mp, "phase": mk * 0.40, "branch_idx": (mk * 2) % 6})
    # body
    smooth_sphere(f"monkey_{mk}_body", r=0.20, segs=16, rings=12, loc=(0, 0, 0), parent=mp, mat=MAT_MONKEY, scale=(1.0, 1.3, 1.0))
    # head
    smooth_sphere(f"monkey_{mk}_head", r=0.15, segs=16, rings=12, loc=(0, 0.30, 0), parent=mp, mat=MAT_MONKEY)
    # face highlight
    smooth_sphere(f"monkey_{mk}_face", r=0.10, segs=14, rings=10, loc=(0, 0.30, 0.10), parent=mp, mat=MAT_MONKEY_FACE, scale=(1.0, 1.0, 0.5))
    # 2 eyes
    for ek, ez in [("L", 0.04), ("R", -0.04)]:
        smooth_sphere(f"monkey_{mk}_eye_{ek}", r=0.022, segs=10, rings=6, loc=(0, 0.32, 0.13 + ez * 0.5), parent=mp, mat=MAT_SLOTH_EYE)
    # 2 ears (round)
    for ek, ez in [("L", 0.13), ("R", -0.13)]:
        smooth_sphere(f"monkey_{mk}_ear_{ek}", r=0.05, segs=10, rings=6, loc=(0, 0.35, ez), parent=mp, mat=MAT_MONKEY)
    # 2 arms hanging from branch (swing)
    for ak, az in [("L", 0.15), ("R", -0.15)]:
        arm_p = empty(f"monkey_{mk}_arm_p_{ak}", (0, 0.20, az), parent=mp)
        arm_p.rotation_euler = (math.radians(120 if az > 0 else -120), 0, 0)
        smooth_cone(f"monkey_{mk}_arm_{ak}", r1=0.05, r2=0.04, depth=0.30, segs=6, loc=(0, -0.15, 0), parent=arm_p, mat=MAT_MONKEY)
    # 2 legs (clutching branch)
    for lk, lz in [("L", 0.10), ("R", -0.10)]:
        leg_p = empty(f"monkey_{mk}_leg_p_{lk}", (0, -0.15, lz), parent=mp)
        leg_p.rotation_euler = (math.radians(70), 0, 0)
        smooth_cone(f"monkey_{mk}_leg_{lk}", r1=0.05, r2=0.04, depth=0.25, segs=6, loc=(0, -0.12, 0), parent=leg_p, mat=MAT_MONKEY)
    # tail (curled)
    tail_p = empty(f"monkey_{mk}_tail_p", (0, -0.10, 0), parent=mp)
    tail_p.rotation_euler = (math.radians(-30), 0, 0)
    for tk in range(4):
        smooth_sphere(f"monkey_{mk}_tail_{tk}", r=0.035, segs=10, rings=6, loc=(0, -0.10 - tk * 0.10, 0), parent=tail_p, mat=MAT_MONKEY)


# --- CASCADE arrière -----------------------------------------------
waterfall_p = empty("waterfall", (-9, 0, -6))
# rock formation
smooth_sphere("waterfall_rock1", r=2.0, segs=18, rings=12, loc=(0, 1.5, 0), parent=waterfall_p, mat=MAT_ROCK)
smooth_sphere("waterfall_rock2", r=1.5, segs=18, rings=12, loc=(0, 3.0, 0), parent=waterfall_p, mat=MAT_ROCK, scale=(1.0, 1.0, 1.2))
# water flowing (8 segments)
waterfall_segs = []
for sg in range(8):
    seg = beveled_cube(f"waterfall_{sg}", (0.55, 0.50, 0.20), bevel_offset=0.03, bevel_segments=2, loc=(0, 3.5 - sg * 0.6, 0.5), parent=waterfall_p, mat=MAT_WATER)
    seg["_seg"] = sg
    waterfall_segs.append(seg)
# pool bottom
smooth_cone("waterfall_pool", r1=1.5, r2=1.5, depth=0.10, segs=22, loc=(0, 0.15, 0), parent=waterfall_p, mat=MAT_WATER)


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

    # 3 paresseux : mouvement très lent (signature)
    for sl in sloths:
        ph = sl["phase"]
        slow_swing = math.radians(3 * math.sin(2 * math.pi * tt * 0.3 + ph))
        kf(sl["p"], f, "rotation_euler", (0, 0, math.radians(-90) + slow_swing))

    # 8 toucans : bec ouvre/ferme
    for tc in toucans:
        ph = tc["phase"]
        beak_open = math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        if beak_open > 0:
            kf(tc["beak"], f, "rotation_euler", (math.radians(beak_open * 15), 0, 0))

    # 8 papillons jungle flap + orbit
    for bf in butterflies:
        ang = bf["a"] + tt * 2 * math.pi * 0.5
        bx_ = math.cos(ang) * bf["r"]
        bz_ = math.sin(ang) * bf["r"]
        by_ = bf["by"] + 0.5 * math.sin(2 * math.pi * tt * 1.5 + bf["phase"])
        kf(bf["p"], f, "location", (bx_, by_, bz_))
        kf(bf["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(60) * math.sin(2 * math.pi * tt * 10 + bf["phase"])
        kf(bf["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(bf["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 4 grenouilles : bondissent (hop)
    for fr in frogs:
        bx_, by_, bz_ = fr["base"]
        ph = fr["phase"]
        # hop pattern (peaks)
        hop_cycle = (tt * 2 + ph) % 1.0
        ny = by_ + 0.6 * max(0, math.sin(hop_cycle * math.pi))
        nx = bx_ + 0.3 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        kf(fr["p"], f, "location", (nx, ny, bz_))
        # rotate slight
        kf(fr["p"], f, "rotation_euler", (0, math.radians(180 * tt + ph * 60), 0))

    # 12 lianas ondulent
    for li in lianas:
        ph = li["phase"]
        sway = math.radians(8 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi))
        kf(li["p"], f, "rotation_euler", (sway, 0, math.radians(5 * math.cos(2 * math.pi * tt * 1.3 + ph * math.pi))))

    # cascade flow (cycle Y)
    for ws in waterfall_segs:
        sg = ws["_seg"]
        offset = -((sg * 0.6) + tt * 3.0) % (8 * 0.6)
        kf(ws, f, "location", (0, 3.5 + offset, 0.5))
        sc = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 5 + sg * 0.4)
        kf(ws, f, "scale", (sc, 1.0, sc))

    # 4 monkeys swing (slight arm sway)
    for mk_obj in monkeys:
        ph = mk_obj["phase"]
        swing = math.radians(5 * math.sin(2 * math.pi * tt * 1.2 + ph * math.pi))
        kf(mk_obj["p"], f, "rotation_euler", (swing, 0, 0))

    # 6 flowers pulse
    for fl in flowers:
        ph = fl["phase"]
        ps = 1.0 + 0.08 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(fl["p"], f, "scale", (ps, ps, ps))

    # 8 fog puffs drift
    for fp in fog_puffs:
        bx_ = fp["_base_x"]
        ph = fp["_phase"]
        nx = bx_ + 0.8 * math.sin(2 * math.pi * tt * 0.3 + ph * math.pi)
        kf(fp, f, "location", (nx, fp.location.y if f > 1 else fp.location.y, fp.location.z if f > 1 else fp.location.z))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_jungle_sloth_canopy] wrote {OUT}")
