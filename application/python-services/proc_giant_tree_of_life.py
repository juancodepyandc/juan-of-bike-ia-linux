"""
proc_giant_tree_of_life.py — 160e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA + MILESTONE 24E QUALITÉ — feedback utilisateur appliqué (smooth + bevels + multi-axes + hierarchy).

Arbre de vie géant fantasy :
- tronc massif multi-segments bevelé avec écorce sculptée
- 8 grosses branches articulées radiales avec sub-branches
- 100 feuilles disposées sur 6 niveaux
- racines exposées avec rocks autour
- cabane elfique perchée dans branches
- 12 lanternes émissives suspendues
- 4 escaliers spiralant tronc
- 6 oiseaux nichant
- 30 papillons fairy émissifs
- pont liana entre 2 grosses branches
- sol mossy + 8 champignons lumineux
- ciel féerique crépuscule
- lune émissive
- 50 lucioles spiralant
- esprit gardien éthéré au sommet

Animations multi-axes simultanées :
- 100 feuilles : wave différentielles + flutter
- 8 grosses branches : sway X+Z phase différentielle
- 12 lanternes : pulse émission + sway suspended
- 30 papillons fairy : orbites 3D différentielles
- 50 lucioles : spirales montantes
- 6 oiseaux : flap + tiny moves
- esprit : pulse + rotate continue + float
- pont liana : oscille léger
- 8 champignons : pulse émission

Sortie : output/3d/pbr_treeoflife_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_treeoflife_proc.glb"))

random.seed(0xCEE1F3)


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
MAT_SKY = make_mat("sky_fae", (0.30, 0.20, 0.45), roughness=1.0, emi=(0.25, 0.15, 0.40), emi_strength=0.9)
MAT_MOON = make_mat("moon", (0.95, 0.92, 0.85), roughness=0.0, emi=(0.95, 0.92, 0.85), emi_strength=8.0)
MAT_MOON_HALO = make_mat("moon_halo", (0.95, 0.92, 0.85), roughness=0.0, alpha=0.30, emi=(0.95, 0.92, 0.85), emi_strength=2.5)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.0)
MAT_BARK = make_mat("bark", (0.30, 0.20, 0.12), roughness=0.95, emi=(0.10, 0.05, 0.03), emi_strength=0.2)
MAT_BARK_DARK = make_mat("bark_dark", (0.18, 0.10, 0.05), roughness=0.95)
MAT_BARK_GLOW = make_mat("bark_glow", (0.55, 0.30, 0.15), roughness=0.6, emi=(0.50, 0.20, 0.10), emi_strength=1.5)
MAT_LEAF_A = make_mat("leaf_A", (0.20, 0.55, 0.25), roughness=0.6, emi=(0.10, 0.30, 0.10), emi_strength=0.6)
MAT_LEAF_B = make_mat("leaf_B", (0.45, 0.75, 0.30), roughness=0.5, emi=(0.20, 0.40, 0.15), emi_strength=0.7)
MAT_LEAF_C = make_mat("leaf_C", (0.85, 0.55, 0.20), roughness=0.5, emi=(0.45, 0.30, 0.10), emi_strength=0.8)
MAT_LEAF_D = make_mat("leaf_D", (0.95, 0.30, 0.55), roughness=0.5, emi=(0.50, 0.10, 0.30), emi_strength=0.9)
MAT_ROOT = make_mat("root", (0.20, 0.12, 0.06), roughness=0.95)
MAT_GROUND = make_mat("ground", (0.10, 0.20, 0.08), roughness=0.85, emi=(0.05, 0.10, 0.05), emi_strength=0.3)
MAT_MOSS = make_mat("moss", (0.20, 0.45, 0.18), roughness=0.7, emi=(0.10, 0.25, 0.10), emi_strength=0.4)
MAT_ROCK = make_mat("rock", (0.28, 0.25, 0.22), roughness=0.95)
MAT_LANTERN = make_mat("lantern", (1.0, 0.65, 0.20), roughness=0.0, emi=(1.0, 0.65, 0.20), emi_strength=12.0)
MAT_LANTERN_FRAME = make_mat("lantern_frame", (0.85, 0.55, 0.20), metallic=0.5, roughness=0.30, emi=(0.30, 0.20, 0.08), emi_strength=0.5)
MAT_CABIN_WALL = make_mat("cabin_wall", (0.55, 0.35, 0.20), roughness=0.7)
MAT_CABIN_ROOF = make_mat("cabin_roof", (0.30, 0.15, 0.10), roughness=0.7)
MAT_CABIN_WINDOW = make_mat("cabin_window", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=10.0)
MAT_STAIRS = make_mat("stairs", (0.40, 0.25, 0.15), roughness=0.7)
MAT_LIANA = make_mat("liana", (0.30, 0.50, 0.20), roughness=0.7)
MAT_BIRD = make_mat("bird", (0.45, 0.30, 0.55), roughness=0.6, emi=(0.20, 0.15, 0.25), emi_strength=0.3)
MAT_FAIRY_A = make_mat("fairy_A", (1.0, 0.40, 0.80), roughness=0.0, emi=(1.0, 0.40, 0.80), emi_strength=9.0)
MAT_FAIRY_B = make_mat("fairy_B", (0.40, 1.0, 0.75), roughness=0.0, emi=(0.40, 1.0, 0.75), emi_strength=9.0)
MAT_FAIRY_C = make_mat("fairy_C", (0.55, 0.80, 1.0), roughness=0.0, emi=(0.55, 0.80, 1.0), emi_strength=9.0)
MAT_FIREFLY = make_mat("firefly", (1.0, 0.95, 0.40), roughness=0.0, emi=(1.0, 0.95, 0.40), emi_strength=10.0)
MAT_MUSHROOM_STEM = make_mat("mushroom_stem", (0.85, 0.80, 0.70), roughness=0.6)
MAT_MUSHROOM_CAP = make_mat("mushroom_cap", (0.55, 0.20, 0.95), roughness=0.4, emi=(0.55, 0.20, 0.95), emi_strength=6.0)
MAT_MUSHROOM_CAP2 = make_mat("mushroom_cap2", (0.20, 0.95, 0.85), roughness=0.4, emi=(0.20, 0.95, 0.85), emi_strength=6.0)
MAT_SPIRIT = make_mat("spirit", (0.85, 0.95, 1.0), roughness=0.0, alpha=0.40, emi=(0.65, 0.85, 1.0), emi_strength=8.0)


# --- backdrop : faerie sky -------------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 26), bevel_offset=0.05, bevel_segments=2, loc=(0, 18, 10), mat=MAT_SKY)

# 40 stars
for i in range(40):
    x = random.uniform(-20, 20)
    z = random.uniform(8, 18)
    y = random.uniform(16, 17.5)
    r = random.uniform(0.07, 0.12)
    smooth_sphere(f"star_{i}", r=r, segs=10, rings=8, loc=(x, y, z), mat=MAT_STAR)

# moon
moon_p = empty("moon_p", (-12, 15, 8))
smooth_sphere("moon", r=1.0, segs=24, rings=18, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON)
moon_halo = smooth_sphere("moon_halo", r=2.0, segs=22, rings=14, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)

# ground mossy
ground = beveled_cube("ground", (30, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND)
# moss patches
for mk in range(8):
    mx = random.uniform(-10, 10)
    mz = random.uniform(-5, 7)
    smooth_sphere(f"moss_{mk}", r=random.uniform(0.5, 1.2), segs=14, rings=8, loc=(mx, 0.05, mz), mat=MAT_MOSS, scale=(1.0, 0.10, 1.0))

# 8 luminescent mushrooms
mushrooms = []
for mk in range(8):
    mx = random.uniform(-9, 9)
    mz = random.uniform(-3, 6)
    if abs(mx) < 2.5 and abs(mz) < 2.5:
        continue
    mp = empty(f"mush_{mk}", (mx, 0, mz))
    mushrooms.append(mp)
    h = random.uniform(0.4, 0.8)
    smooth_cone(f"mush_{mk}_stem", r1=0.10, r2=0.07, depth=h, segs=10, loc=(0, h / 2, 0), parent=mp, mat=MAT_MUSHROOM_STEM)
    cap_mat = MAT_MUSHROOM_CAP if mk % 2 == 0 else MAT_MUSHROOM_CAP2
    smooth_sphere(f"mush_{mk}_cap", r=0.30, segs=18, rings=12, loc=(0, h + 0.10, 0), parent=mp, mat=cap_mat, scale=(1.0, 0.55, 1.0))
    mp["_phase"] = mk * 0.30


# --- main trunk (5 segments tapered) --------------------------------------
trunk_p = empty("trunk_p", (0, 0, 0))
TRUNK_SEGMENTS = [(1.2, 1.05, 2.0), (1.05, 0.95, 2.2), (0.95, 0.80, 2.0), (0.80, 0.60, 1.8), (0.60, 0.40, 1.6)]
cur_y = 0
trunk_pts = []
for ts, (r1, r2, h) in enumerate(TRUNK_SEGMENTS):
    seg = smooth_cone(f"trunk_{ts}", r1=r1, r2=r2, depth=h, segs=20, loc=(0, cur_y + h / 2, 0), parent=trunk_p, mat=MAT_BARK)
    # sculpted detail : 3 ring barks
    for kk in range(3):
        y_ring = cur_y + (kk + 1) * (h / 4)
        ring_r = r1 + (r2 - r1) * (kk + 1) / 4
        for ka in range(6):
            ang = ka * (math.pi * 2 / 6)
            smooth_sphere(f"trunk_{ts}_bk_{kk}_{ka}", r=0.08, segs=10, rings=8, loc=(math.cos(ang) * ring_r * 1.02, y_ring, math.sin(ang) * ring_r * 1.02), parent=trunk_p, mat=MAT_BARK_DARK, scale=(0.7, 1.5, 0.7))
    # glowing veins (4 around)
    for vk in range(4):
        va = vk * (math.pi * 2 / 4)
        vein = smooth_cone(f"trunk_{ts}_vein_{vk}", r1=0.03, r2=0.03, depth=h * 0.85, segs=6, loc=(math.cos(va) * (r1 - 0.05), cur_y + h / 2, math.sin(va) * (r1 - 0.05)), parent=trunk_p, mat=MAT_BARK_GLOW)
    trunk_pts.append((cur_y, r1, r2))
    cur_y += h

TRUNK_TOP = cur_y

# --- 8 grosses branches articulées radiales -------------------------------
branches = []
for bk in range(8):
    ba = bk * (math.pi * 2 / 8) + random.uniform(-0.1, 0.1)
    by = TRUNK_TOP - 2.0 - (bk % 3) * 1.5  # distributed at different heights
    branch_p = empty(f"branch_{bk}_p", (math.cos(ba) * 0.50, by, math.sin(ba) * 0.50))
    branches.append(branch_p)
    branch_p.parent = trunk_p
    branch_p.rotation_euler = (0, -ba, math.radians(45 - (bk % 3) * 10))
    # main branch (cone tapered, horizontal)
    branch_main = smooth_cone(f"branch_{bk}_main", r1=0.35, r2=0.15, depth=3.0, segs=12, loc=(0, 0, 0), parent=branch_p, mat=MAT_BARK)
    branch_main.rotation_euler = (0, 0, math.radians(-90))
    # 3 sub-branches near tip
    for sb in range(3):
        sba = sb * (math.pi * 2 / 3) + 0.3
        sub_p = empty(f"branch_{bk}_sub_p_{sb}", (2.5, 0, 0), parent=branch_p)
        sub_p.rotation_euler = (math.radians(20 * math.cos(sba)), 0, math.radians(20 * math.sin(sba)))
        sub_branch = smooth_cone(f"branch_{bk}_sub_{sb}", r1=0.10, r2=0.04, depth=1.4, segs=8, loc=(0.65, 0, 0), parent=sub_p, mat=MAT_BARK)
        sub_branch.rotation_euler = (0, 0, math.radians(-90))
        # 6 leaves per sub-branch
        for lf in range(6):
            la = lf * (math.pi * 2 / 6)
            lx = 0.30 + lf * 0.18
            lz = math.cos(la) * 0.18
            ly = math.sin(la) * 0.18
            lm = [MAT_LEAF_A, MAT_LEAF_B, MAT_LEAF_C, MAT_LEAF_D][lf % 4]
            leaf_p = empty(f"branch_{bk}_sub_{sb}_leaf_p_{lf}", (lx, ly, lz), parent=sub_p)
            leaf = smooth_sphere(f"branch_{bk}_sub_{sb}_leaf_{lf}", r=0.20, segs=12, rings=8, loc=(0, 0, 0), parent=leaf_p, mat=lm, scale=(1.5, 0.10, 0.8))
            leaf_p["_phase"] = (bk * 3 + sb) * 0.20 + lf * 0.07

# --- additional 30 leaves around top --------------------------------------
top_leaves = []
for lk in range(30):
    a = lk * (math.pi * 2 / 30)
    r = random.uniform(2.5, 4.5)
    y = TRUNK_TOP - 0.5 + random.uniform(-0.5, 2.0)
    x = math.cos(a) * r
    z = math.sin(a) * r
    lm = [MAT_LEAF_A, MAT_LEAF_B, MAT_LEAF_C, MAT_LEAF_D][lk % 4]
    lp = empty(f"top_leaf_p_{lk}", (x, y, z))
    leaf = smooth_sphere(f"top_leaf_{lk}", r=0.20, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=lm, scale=(1.5, 0.10, 0.8))
    lp["_phase"] = lk * 0.13
    top_leaves.append(lp)


# --- exposed roots --------------------------------------------------------
for rk in range(8):
    ra = rk * (math.pi * 2 / 8) + random.uniform(-0.1, 0.1)
    rx = math.cos(ra) * 1.5
    rz = math.sin(ra) * 1.5
    root = smooth_cone(f"root_{rk}", r1=0.25, r2=0.10, depth=1.5, segs=10, loc=(rx, 0.20, rz), mat=MAT_ROOT)
    root.rotation_euler = (math.radians(75 * math.cos(ra)), 0, math.radians(75 * math.sin(ra)))


# --- cabane elfique (perchée dans branches) ------------------------------
cabin_p = empty("cabin_p", (3.5, 5.5, 0))
# main walls
cabin_walls = beveled_cube("cabin_walls", (1.2, 1.0, 1.0), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.50, 0), parent=cabin_p, mat=MAT_CABIN_WALL)
# roof (cone)
smooth_cone("cabin_roof", r1=0.85, r2=0.0, depth=0.80, segs=12, loc=(0, 1.40, 0), parent=cabin_p, mat=MAT_CABIN_ROOF)
# 2 windows émissifs
for wx, wz in [(0.40, 0.51), (-0.40, 0.51)]:
    smooth_sphere(f"cabin_win_{wx}", r=0.15, segs=14, rings=10, loc=(wx, 0.65, wz), parent=cabin_p, mat=MAT_CABIN_WINDOW, scale=(1.0, 1.0, 0.20))
# door
beveled_cube("cabin_door", (0.30, 0.50, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.25, 0.52), parent=cabin_p, mat=MAT_CABIN_ROOF)
# chimney
smooth_cone("cabin_chim", r1=0.10, r2=0.08, depth=0.50, segs=8, loc=(0.30, 1.70, 0), parent=cabin_p, mat=MAT_BARK_DARK)


# --- 12 hanging lanternes émissives ---------------------------------------
lanterns = []
LANT_POSITIONS = []
for lk in range(12):
    la = lk * (math.pi * 2 / 12)
    lr = 3.5 + (lk % 3) * 0.4
    ly = TRUNK_TOP - 0.5 - (lk % 4) * 1.2
    lx = math.cos(la) * lr
    lz = math.sin(la) * lr
    LANT_POSITIONS.append((lx, ly, lz))

for li, (lx, ly, lz) in enumerate(LANT_POSITIONS):
    lp = empty(f"lant_p_{li}", (lx, ly, lz))
    # chain
    smooth_cone(f"lant_{li}_chain", r1=0.015, r2=0.015, depth=0.60, segs=4, loc=(0, 0.35, 0), parent=lp, mat=MAT_LANTERN_FRAME)
    # body (small sphere with frame)
    smooth_sphere(f"lant_{li}_body", r=0.15, segs=14, rings=10, loc=(0, 0, 0), parent=lp, mat=MAT_LANTERN_FRAME, scale=(1.0, 1.2, 1.0))
    # glowing core
    smooth_sphere(f"lant_{li}_core", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_LANTERN)
    # bottom finial
    smooth_cone(f"lant_{li}_fin", r1=0.06, r2=0.0, depth=0.10, segs=8, loc=(0, -0.18, 0), parent=lp, mat=MAT_LANTERN_FRAME)
    lp["_phase"] = li * 0.30
    lp["_base"] = (lx, ly, lz)
    lanterns.append(lp)


# --- 4 escaliers spiralant tronc (4 platform sections) -------------------
for sk in range(4):
    sa = sk * (math.pi / 2)
    sy = 1.0 + sk * 2.0
    sx = math.cos(sa) * 1.5
    sz = math.sin(sa) * 1.5
    # platform
    beveled_cube(f"stair_{sk}", (0.80, 0.10, 0.40), bevel_offset=0.03, bevel_segments=2, loc=(sx, sy, sz), mat=MAT_STAIRS)


# --- pont liana entre 2 branches (curving) -------------------------------
liana_p = empty("liana_p", (-2.5, 5.0, 0))
# 8 segs forming arc
for lk in range(8):
    t_seg = lk / 7
    seg_y = 0.30 * math.sin(math.pi * t_seg)
    seg_x = -2.0 + t_seg * 4.0
    seg = smooth_cone(f"liana_{lk}", r1=0.06, r2=0.06, depth=0.45, segs=6, loc=(seg_x, seg_y, 0), parent=liana_p, mat=MAT_LIANA)
    seg.rotation_euler = (0, 0, math.radians(90))


# --- 6 oiseaux nichant sur branches --------------------------------------
birds = []
for bk in range(6):
    ba = bk * (math.pi * 2 / 6) + 0.5
    by = TRUNK_TOP - 1.5 - (bk % 2) * 1.5
    bx = math.cos(ba) * 2.5
    bz = math.sin(ba) * 2.5
    bp = empty(f"bird_{bk}_p", (bx, by, bz))
    birds.append({"p": bp, "phase": bk * 0.5})
    # body
    smooth_sphere(f"bird_{bk}_body", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD, scale=(1.3, 0.85, 0.85))
    # head
    smooth_sphere(f"bird_{bk}_head", r=0.06, segs=10, rings=8, loc=(0.10, 0.05, 0), parent=bp, mat=MAT_BIRD)
    # beak
    smooth_cone(f"bird_{bk}_beak", r1=0.02, r2=0.0, depth=0.06, segs=6, loc=(0.16, 0.05, 0), parent=bp, mat=MAT_LANTERN_FRAME)
    # 2 wings
    wL = empty(f"bird_{bk}_wL", (0, 0.02, 0.05), parent=bp)
    wR = empty(f"bird_{bk}_wR", (0, 0.02, -0.05), parent=bp)
    smooth_sphere(f"bird_{bk}_wL_b", r=0.08, segs=10, rings=6, loc=(0, 0, 0.10), parent=wL, mat=MAT_BIRD, scale=(0.7, 0.05, 1.5))
    smooth_sphere(f"bird_{bk}_wR_b", r=0.08, segs=10, rings=6, loc=(0, 0, -0.10), parent=wR, mat=MAT_BIRD, scale=(0.7, 0.05, 1.5))
    birds[bk]["wL"] = wL
    birds[bk]["wR"] = wR


# --- 30 papillons fairy émissifs ----------------------------------------
fairies = []
FAIRY_MATS = [MAT_FAIRY_A, MAT_FAIRY_B, MAT_FAIRY_C]
for fk in range(30):
    a = fk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(2.5, 6.0)
    y = random.uniform(2.5, 11)
    fp = empty(f"fairy_{fk}_p", (math.cos(a) * r, y, math.sin(a) * r))
    mat = FAIRY_MATS[fk % 3]
    # body
    smooth_sphere(f"fairy_{fk}_body", r=0.08, segs=10, rings=6, loc=(0, 0, 0), parent=fp, mat=mat)
    # 2 wings émissives
    wL = empty(f"fairy_{fk}_wL", (0, 0, 0.03), parent=fp)
    wR = empty(f"fairy_{fk}_wR", (0, 0, -0.03), parent=fp)
    smooth_sphere(f"fairy_{fk}_wL_b", r=0.10, segs=10, rings=6, loc=(0, 0, 0.08), parent=wL, mat=mat, scale=(1.0, 0.05, 1.4))
    smooth_sphere(f"fairy_{fk}_wR_b", r=0.10, segs=10, rings=6, loc=(0, 0, -0.08), parent=wR, mat=mat, scale=(1.0, 0.05, 1.4))
    fairies.append({"p": fp, "wL": wL, "wR": wR, "a": a, "r": r, "y": y, "phase": fk * 0.4})


# --- 50 lucioles spiralant montantes -------------------------------------
fireflies = []
for fk in range(50):
    a = fk * (math.pi * 2 / 50) + random.uniform(-0.2, 0.2)
    r = random.uniform(2, 8)
    y = random.uniform(0.5, 11)
    fp = smooth_sphere(f"firefly_{fk}", r=random.uniform(0.05, 0.08), segs=8, rings=6, loc=(math.cos(a) * r, y, math.sin(a) * r), mat=MAT_FIREFLY)
    fp["_a"] = a
    fp["_r0"] = r
    fp["_y0"] = y
    fp["_phase"] = fk * 0.18
    fireflies.append(fp)


# --- esprit gardien éthéré au sommet -------------------------------------
spirit_p = empty("spirit_p", (0, TRUNK_TOP + 2.5, 0))
# body
smooth_cone("spirit_body", r1=0.30, r2=0.55, depth=1.2, segs=14, loc=(0, 0, 0), parent=spirit_p, mat=MAT_SPIRIT)
# head
smooth_sphere("spirit_head", r=0.35, segs=18, rings=12, loc=(0, 0.65, 0), parent=spirit_p, mat=MAT_SPIRIT)
# 2 glowing eyes
for ez in [0.10, -0.10]:
    smooth_sphere(f"spirit_eye_{ez}", r=0.04, segs=10, rings=6, loc=(0.25, 0.75, ez), parent=spirit_p, mat=MAT_FAIRY_C)
# 2 arms (tapered ghostly)
for ak, az in [("L", 0.30), ("R", -0.30)]:
    arm = smooth_cone(f"spirit_arm_{ak}", r1=0.10, r2=0.05, depth=0.60, segs=10, loc=(0.20, 0.10, az), parent=spirit_p, mat=MAT_SPIRIT)
    arm.rotation_euler = (0, 0, math.radians(-50 if az > 0 else 50))


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


# Find all leaf_p objects for animation (those linking to branch_X_sub_Y_leaf_p_Z)
leaf_ps = [obj for obj in bpy.data.objects if obj.name.startswith("branch_") and "_leaf_p_" in obj.name]

for f in range(1, FRAMES + 1):
    t = (f - 1) * DT
    tt = t / DURATION

    # 8 main branches sway X+Z
    for bi, bp_obj in enumerate(branches):
        bx_sway = math.radians(5) * math.sin(2 * math.pi * tt * 0.8 + bi * 0.5)
        bz_sway = math.radians(4) * math.cos(2 * math.pi * tt * 0.9 + bi * 0.4)
        ba = bi * (math.pi * 2 / 8) + random.uniform(-0.1, 0.1)
        # preserve base rotation while adding sway
        base_yaw = -ba
        base_pitch = math.radians(45 - (bi % 3) * 10)
        kf(bp_obj, f, "rotation_euler", (bx_sway, base_yaw, base_pitch + bz_sway))

    # leaves on sub-branches : flutter
    for lp_obj in leaf_ps:
        phase = lp_obj.get("_phase", 0.0)
        fx = math.radians(20) * math.sin(2 * math.pi * tt * 3 + phase * math.pi * 2)
        fz = math.radians(15) * math.cos(2 * math.pi * tt * 2.5 + phase * math.pi * 2)
        kf(lp_obj, f, "rotation_euler", (fx, 0, fz))

    # 30 top leaves wave
    for lp_obj in top_leaves:
        phase = lp_obj["_phase"]
        fx = math.radians(15) * math.sin(2 * math.pi * tt * 2.5 + phase * math.pi)
        fz = math.radians(10) * math.cos(2 * math.pi * tt * 2.2 + phase * math.pi)
        kf(lp_obj, f, "rotation_euler", (fx, 0, fz))

    # 12 lanterns : pulse + sway
    for lp_obj in lanterns:
        phase = lp_obj["_phase"]
        bx, by, bz = lp_obj["_base"]
        sway_x = bx + 0.15 * math.sin(2 * math.pi * tt * 1.5 + phase * math.pi)
        sway_z = bz + 0.10 * math.cos(2 * math.pi * tt * 1.7 + phase * math.pi)
        kf(lp_obj, f, "location", (sway_x, by, sway_z))
        ps = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2.5 + phase * math.pi)
        kf(lp_obj, f, "scale", (ps, ps, ps))

    # 30 papillons fairy : orbites 3D + flap
    for fd in fairies:
        ang = fd["a"] + tt * 2 * math.pi * 0.5
        bx_ = math.cos(ang) * fd["r"]
        bz_ = math.sin(ang) * fd["r"]
        by_ = fd["y"] + 0.4 * math.sin(2 * math.pi * tt * 1.8 + fd["phase"])
        kf(fd["p"], f, "location", (bx_, by_, bz_))
        kf(fd["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(50) * math.sin(2 * math.pi * tt * 10 + fd["phase"])
        kf(fd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(fd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 50 fireflies : spiral upward
    for fp_obj in fireflies:
        a0 = fp_obj["_a"]
        r0 = fp_obj["_r0"]
        y0 = fp_obj["_y0"]
        ph = fp_obj["_phase"]
        spiral_ang = a0 + tt * 2 * math.pi * 0.8
        spiral_r = r0 + 0.5 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi)
        ny = y0 + 0.5 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        nx = math.cos(spiral_ang) * spiral_r
        nz = math.sin(spiral_ang) * spiral_r
        kf(fp_obj, f, "location", (nx, ny, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(fp_obj, f, "scale", (sc, sc, sc))

    # 6 birds : flap + tiny moves
    for bd in birds:
        ph = bd["phase"]
        wflap = math.radians(35) * math.sin(2 * math.pi * tt * 6 + ph)
        kf(bd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(bd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # esprit : pulse + rotate continue + float
    sy = TRUNK_TOP + 2.5 + 0.3 * math.sin(2 * math.pi * tt * 1.0)
    kf(spirit_p, f, "location", (0, sy, 0))
    kf(spirit_p, f, "rotation_euler", (math.radians(10 * math.sin(2 * math.pi * tt * 1.5)), math.radians(60 * tt * 360 / 360), 0))
    sps = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2)
    kf(spirit_p, f, "scale", (sps, sps, sps))

    # pont liana : oscille léger
    kf(liana_p, f, "rotation_euler", (0, 0, math.radians(3 * math.sin(2 * math.pi * tt * 1.5))))

    # 8 mushrooms pulse
    for mp_obj in mushrooms:
        ph = mp_obj["_phase"]
        ms = 1.0 + 0.08 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(mp_obj, f, "scale", (ms, ms, ms))

    # moon halo breathe
    mh = 1.0 + 0.12 * math.sin(2 * math.pi * tt * 1.5)
    kf(moon_halo, f, "scale", (mh, mh, mh))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_giant_tree_of_life] wrote {OUT}")
