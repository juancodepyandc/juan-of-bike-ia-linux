"""
proc_art_museum_gallery.py — 165e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Galerie musée d'art avec Vénus de Milo centrale :
- grande galerie marbre + parquet
- 8 colonnes ioniques avec chapiteau et volutes
- plafond cassettes
- **Vénus de Milo centrale** anatomie (torso féminin sans bras + drapé + base)
- 6 sculptures sur piédestaux (bustes + corps)
- 12 tableaux dorés au mur (cadres ornés + toiles colorées émissives)
- 4 bancs visiteurs bois
- 4 spotlights émissifs orientables
- 3 vases anciens grecs avec dessins
- bouquet fleurs sur piédestal
- 6 visiteurs silhouettes
- horloge ronde mur
- 2 grandes fenêtres avec ciel matin doré
- carpet rouge central
- balustrade gold

Animations multi-axes simultanées :
- 4 spotlights pulse intensité + sweep angle
- 12 tableaux pulse subtile émission
- 6 visiteurs walk slow + tête tourne légère
- horloge 2 aiguilles
- bouquet fleurs ondule
- carpet effleurement
- 3 vases rotation léger sur axes

Sortie : output/3d/pbr_museum_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_museum_proc.glb"))

random.seed(0xA27ECC)


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
MAT_MARBLE_WHITE = make_mat("marble_white", (0.92, 0.90, 0.85), roughness=0.40, emi=(0.30, 0.30, 0.28), emi_strength=0.3)
MAT_MARBLE_CREAM = make_mat("marble_cream", (0.88, 0.82, 0.70), roughness=0.45, emi=(0.30, 0.28, 0.22), emi_strength=0.3)
MAT_PARQUET = make_mat("parquet", (0.50, 0.30, 0.15), roughness=0.55, emi=(0.18, 0.10, 0.05), emi_strength=0.2)
MAT_CEILING = make_mat("ceiling", (0.85, 0.78, 0.65), roughness=0.55, emi=(0.30, 0.25, 0.20), emi_strength=0.3)
MAT_GOLD = make_mat("gold", (0.95, 0.75, 0.30), metallic=0.95, roughness=0.25, emi=(0.45, 0.35, 0.15), emi_strength=0.6)
MAT_GOLD_ORNATE = make_mat("gold_ornate", (1.0, 0.85, 0.40), metallic=0.95, roughness=0.15, emi=(0.60, 0.45, 0.20), emi_strength=0.8)
MAT_STONE_DARK = make_mat("stone_dark", (0.45, 0.42, 0.38), roughness=0.7)
MAT_DRAPE = make_mat("drape", (0.85, 0.85, 0.80), roughness=0.6, emi=(0.30, 0.30, 0.28), emi_strength=0.3)
MAT_VENUS = make_mat("venus", (0.92, 0.90, 0.85), roughness=0.30, emi=(0.40, 0.40, 0.38), emi_strength=0.5)
MAT_SPOT_HOUSING = make_mat("spot_housing", (0.30, 0.25, 0.22), metallic=0.5, roughness=0.50)
MAT_SPOT_LIGHT = make_mat("spot_light", (1.0, 0.95, 0.65), roughness=0.0, emi=(1.0, 0.95, 0.65), emi_strength=18.0)
MAT_PAINT_FRAME = make_mat("paint_frame", (0.85, 0.65, 0.20), metallic=0.85, roughness=0.30, emi=(0.45, 0.30, 0.10), emi_strength=0.5)
MAT_PAINT_A = make_mat("paint_A", (0.65, 0.35, 0.40), roughness=0.5, emi=(0.35, 0.15, 0.18), emi_strength=1.5)
MAT_PAINT_B = make_mat("paint_B", (0.35, 0.55, 0.65), roughness=0.5, emi=(0.15, 0.30, 0.35), emi_strength=1.5)
MAT_PAINT_C = make_mat("paint_C", (0.85, 0.75, 0.45), roughness=0.5, emi=(0.45, 0.40, 0.20), emi_strength=1.5)
MAT_PAINT_D = make_mat("paint_D", (0.30, 0.45, 0.30), roughness=0.5, emi=(0.15, 0.25, 0.15), emi_strength=1.5)
MAT_BENCH_WOOD = make_mat("bench_wood", (0.30, 0.18, 0.08), roughness=0.7)
MAT_BENCH_FAB = make_mat("bench_fab", (0.55, 0.20, 0.20), roughness=0.7, emi=(0.18, 0.05, 0.05), emi_strength=0.3)
MAT_VASE_A = make_mat("vase_A", (0.85, 0.55, 0.30), roughness=0.5, emi=(0.35, 0.20, 0.10), emi_strength=0.5)
MAT_VASE_B = make_mat("vase_B", (0.20, 0.15, 0.10), roughness=0.6)
MAT_CARPET = make_mat("carpet_red", (0.75, 0.20, 0.18), roughness=0.85, emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_FLOWER_A = make_mat("flower_A", (0.95, 0.40, 0.55), roughness=0.4, emi=(0.45, 0.15, 0.20), emi_strength=0.6)
MAT_FLOWER_B = make_mat("flower_B", (1.0, 0.85, 0.30), roughness=0.4, emi=(0.50, 0.40, 0.10), emi_strength=0.6)
MAT_FLOWER_STEM = make_mat("flower_stem", (0.20, 0.50, 0.20), roughness=0.7)
MAT_VISITOR = make_mat("visitor", (0.30, 0.30, 0.35), roughness=0.7)
MAT_VISITOR_DARK = make_mat("visitor_dark", (0.15, 0.15, 0.20), roughness=0.7)
MAT_CLOCK_FACE = make_mat("clock_face", (0.92, 0.85, 0.65), roughness=0.40, emi=(0.35, 0.30, 0.20), emi_strength=0.6)
MAT_CLOCK_HAND = make_mat("clock_hand", (0.15, 0.10, 0.08), metallic=0.50, roughness=0.40)
MAT_WINDOW = make_mat("window", (0.95, 0.85, 0.55), roughness=0.0, emi=(0.95, 0.85, 0.55), emi_strength=8.0)
MAT_PEDESTAL = make_mat("pedestal", (0.30, 0.27, 0.24), roughness=0.7)


# --- backdrop : gallery space ----------------------------------------------
back_wall = beveled_cube("back_wall", (20, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 4, 5), mat=MAT_MARBLE_WHITE)
side_wall_L = beveled_cube("side_wall_L", (0.2, 8, 12), bevel_offset=0.05, bevel_segments=2, loc=(-10, 4, 0), mat=MAT_MARBLE_WHITE)
side_wall_R = beveled_cube("side_wall_R", (0.2, 8, 12), bevel_offset=0.05, bevel_segments=2, loc=(10, 4, 0), mat=MAT_MARBLE_WHITE)
floor = beveled_cube("floor", (20, 0.1, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_PARQUET)
ceiling = beveled_cube("ceiling", (20, 0.1, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, 8.05, 0), mat=MAT_CEILING)

# carpet rouge central
carpet = beveled_cube("carpet_runner", (12, 0.05, 2), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.02, 0), mat=MAT_CARPET)

# 2 grandes fenêtres avec ciel doré
for wi, wx in [(0, -3), (1, 3)]:
    win_p = empty(f"window_{wi}_p", (wx, 4, 4.95))
    # frame
    beveled_cube(f"window_{wi}_frame", (2.2, 4.0, 0.10), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=win_p, mat=MAT_GOLD)
    # glow (sky visible)
    beveled_cube(f"window_{wi}_glow", (2.0, 3.8, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.07), parent=win_p, mat=MAT_WINDOW)


# --- 8 colonnes ioniques avec chapiteau et volutes -----------------------
COLUMN_POSITIONS = [(-7, 0, -3), (-3, 0, -3), (3, 0, -3), (7, 0, -3), (-7, 0, 3), (-3, 0, 3), (3, 0, 3), (7, 0, 3)]
for ci, (cx, cy, cz) in enumerate(COLUMN_POSITIONS):
    col_p = empty(f"column_{ci}_p", (cx, cy, cz))
    # 3 drum sections
    for sg in range(3):
        smooth_cone(f"col_{ci}_drum_{sg}", r1=0.30, r2=0.28, depth=2.0, segs=18, loc=(0, 0.5 + sg * 2.0, 0), parent=col_p, mat=MAT_MARBLE_CREAM)
        # flutes
        for fl in range(6):
            fa = fl * (math.pi * 2 / 6)
            smooth_cone(f"col_{ci}_fl_{sg}_{fl}", r1=0.025, r2=0.025, depth=1.9, segs=4, loc=(math.cos(fa) * 0.31, 0.5 + sg * 2.0, math.sin(fa) * 0.31), parent=col_p, mat=MAT_MARBLE_WHITE)
    # base
    smooth_cone(f"col_{ci}_base", r1=0.45, r2=0.35, depth=0.20, segs=18, loc=(0, 0.10, 0), parent=col_p, mat=MAT_MARBLE_CREAM)
    # capital
    smooth_cone(f"col_{ci}_cap", r1=0.38, r2=0.38, depth=0.18, segs=18, loc=(0, 6.60, 0), parent=col_p, mat=MAT_MARBLE_CREAM)
    # 2 volutes
    for vk, vx in [(0, -0.25), (1, 0.25)]:
        smooth_sphere(f"col_{ci}_vol_{vk}", r=0.12, segs=14, rings=10, loc=(vx, 6.70, 0), parent=col_p, mat=MAT_MARBLE_WHITE, scale=(1.0, 0.50, 1.4))


# --- VÉNUS DE MILO centrale -----------------------------------------------
venus_p = empty("venus_p", (0, 0, 0))
# base
pedestal_base = beveled_cube("venus_base", (1.4, 1.2, 1.2), bevel_offset=0.06, bevel_segments=3, loc=(0, 0.60, 0), parent=venus_p, mat=MAT_PEDESTAL)
# torso lower (drapé)
torso_lower = smooth_cone("venus_lower", r1=0.55, r2=0.45, depth=1.5, segs=22, loc=(0, 1.95, 0), parent=venus_p, mat=MAT_VENUS)
# drapé folds (3 verticals)
for dk in range(5):
    da = dk * (math.pi * 2 / 5) + 0.3
    smooth_cone(f"venus_fold_{dk}", r1=0.04, r2=0.02, depth=1.2, segs=6, loc=(math.cos(da) * 0.50, 1.95, math.sin(da) * 0.50), parent=venus_p, mat=MAT_VENUS)
# torso upper (waist)
torso_upper = smooth_sphere("venus_torso", r=0.50, segs=22, rings=16, loc=(0, 3.20, 0), parent=venus_p, mat=MAT_VENUS, scale=(1.0, 1.2, 0.85))
# breasts (anatomical)
for bk, bz in [("L", 0.18), ("R", -0.18)]:
    smooth_sphere(f"venus_breast_{bk}", r=0.18, segs=16, rings=12, loc=(0.40, 3.40, bz), parent=venus_p, mat=MAT_VENUS)
# shoulders (broken stumps where arms were)
for sk, sz in [("L", 0.30), ("R", -0.30)]:
    smooth_sphere(f"venus_shoulder_{sk}", r=0.20, segs=14, rings=10, loc=(0.20, 3.80, sz), parent=venus_p, mat=MAT_VENUS, scale=(1.0, 0.8, 1.0))
# neck
smooth_cone("venus_neck", r1=0.12, r2=0.10, depth=0.20, segs=14, loc=(0, 4.10, 0), parent=venus_p, mat=MAT_VENUS)
# head
smooth_sphere("venus_head", r=0.28, segs=22, rings=18, loc=(0, 4.35, 0), parent=venus_p, mat=MAT_VENUS, scale=(0.95, 1.10, 0.95))
# hair bun back
smooth_sphere("venus_hair", r=0.20, segs=18, rings=14, loc=(-0.20, 4.50, 0), parent=venus_p, mat=MAT_VENUS, scale=(1.2, 0.85, 1.0))
# nose
smooth_cone("venus_nose", r1=0.04, r2=0.03, depth=0.08, segs=8, loc=(0.22, 4.30, 0), parent=venus_p, mat=MAT_VENUS)


# --- 6 sculptures sur piédestaux autour ---------------------------------
SCULP_POSITIONS = [(-6, 0, 0), (6, 0, 0), (-6, 0, -1.5), (6, 0, -1.5), (-8, 0, 1.5), (8, 0, 1.5)]
sculptures = []
for si, (sx, sy, sz) in enumerate(SCULP_POSITIONS):
    sp = empty(f"sculp_{si}_p", (sx, sy, sz))
    sculptures.append(sp)
    # pedestal
    beveled_cube(f"sculp_{si}_ped", (0.85, 1.5, 0.85), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.75, 0), parent=sp, mat=MAT_PEDESTAL)
    # bust or body
    if si % 2 == 0:
        # bust
        smooth_sphere(f"sculp_{si}_torso", r=0.30, segs=20, rings=14, loc=(0, 1.85, 0), parent=sp, mat=MAT_VENUS, scale=(1.0, 1.1, 0.85))
        smooth_sphere(f"sculp_{si}_head", r=0.20, segs=18, rings=14, loc=(0, 2.25, 0), parent=sp, mat=MAT_VENUS)
        smooth_sphere(f"sculp_{si}_hair", r=0.15, segs=14, rings=10, loc=(-0.10, 2.35, 0), parent=sp, mat=MAT_VENUS, scale=(1.2, 0.85, 1.0))
    else:
        # body figure (smaller venus-like)
        smooth_cone(f"sculp_{si}_lower", r1=0.35, r2=0.25, depth=0.85, segs=18, loc=(0, 1.85, 0), parent=sp, mat=MAT_VENUS)
        smooth_sphere(f"sculp_{si}_torso2", r=0.30, segs=20, rings=14, loc=(0, 2.55, 0), parent=sp, mat=MAT_VENUS, scale=(1.0, 1.2, 0.85))
        smooth_sphere(f"sculp_{si}_head2", r=0.18, segs=16, rings=12, loc=(0, 2.95, 0), parent=sp, mat=MAT_VENUS)


# --- 12 tableaux dorés au mur -------------------------------------------
paint_mats = [MAT_PAINT_A, MAT_PAINT_B, MAT_PAINT_C, MAT_PAINT_D]
paintings = []
# back wall (8 paintings)
for pi in range(8):
    px = -7 + pi * 2
    py = 4.5
    pz = 4.85
    pp = empty(f"paint_{pi}_p", (px, py, pz))
    # ornate frame
    beveled_cube(f"paint_{pi}_frame", (1.5, 1.8, 0.12), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=pp, mat=MAT_GOLD_ORNATE)
    # painting canvas
    beveled_cube(f"paint_{pi}_canvas", (1.3, 1.6, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.07), parent=pp, mat=paint_mats[pi % 4])
    paintings.append({"p": pp, "phase": pi * 0.20})
# 2 paintings on each side wall (4 total)
for pi, (px, pz) in enumerate([(-9.85, -2), (-9.85, 2), (9.85, -2), (9.85, 2)]):
    pp = empty(f"paint_side_{pi}_p", (px, 4, pz))
    pp.rotation_euler = (0, math.radians(-90 if px < 0 else 90), 0)
    beveled_cube(f"paint_side_{pi}_frame", (1.4, 1.7, 0.12), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=pp, mat=MAT_GOLD_ORNATE)
    beveled_cube(f"paint_side_{pi}_canvas", (1.2, 1.5, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.07), parent=pp, mat=paint_mats[pi % 4])
    paintings.append({"p": pp, "phase": (8 + pi) * 0.20})


# --- 4 bancs visiteurs --------------------------------------------------
for bi, (bx, bz) in enumerate([(-4, 2), (4, 2), (-4, -2), (4, -2)]):
    bp = empty(f"bench_{bi}_p", (bx, 0, bz))
    bp.rotation_euler = (0, 0, 0)
    # cushion
    beveled_cube(f"bench_{bi}_cush", (1.4, 0.10, 0.45), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.50, 0), parent=bp, mat=MAT_BENCH_FAB)
    # 4 legs
    for lx, lz in [(-0.60, -0.18), (0.60, -0.18), (-0.60, 0.18), (0.60, 0.18)]:
        smooth_cone(f"bench_{bi}_leg_{lx}_{lz}", r1=0.05, r2=0.04, depth=0.50, segs=8, loc=(lx, 0.25, lz), parent=bp, mat=MAT_BENCH_WOOD)


# --- 4 spotlights orientables -------------------------------------------
spotlights = []
SPOT_POSITIONS = [(-5, 7.5, 0), (5, 7.5, 0), (0, 7.5, -3), (0, 7.5, 3)]
for sli, (sx, sy, sz) in enumerate(SPOT_POSITIONS):
    sp = empty(f"spot_{sli}_p", (sx, sy, sz))
    spotlights.append(sp)
    # mounting bracket
    smooth_cone(f"spot_{sli}_mount", r1=0.05, r2=0.05, depth=0.40, segs=8, loc=(0, -0.20, 0), parent=sp, mat=MAT_SPOT_HOUSING)
    # housing (cone pointing down to angle)
    housing_p = empty(f"spot_{sli}_h_p", (0, -0.40, 0), parent=sp)
    housing_p.rotation_euler = (math.radians(35 + (sli % 2) * 20 * (1 if sli < 2 else -1)), 0, math.radians(15 if sli == 0 else (-15 if sli == 1 else 0)))
    smooth_cone(f"spot_{sli}_housing", r1=0.18, r2=0.22, depth=0.30, segs=14, loc=(0, -0.20, 0), parent=housing_p, mat=MAT_SPOT_HOUSING)
    # light source
    smooth_sphere(f"spot_{sli}_light", r=0.15, segs=14, rings=10, loc=(0, -0.40, 0), parent=housing_p, mat=MAT_SPOT_LIGHT)
    sp["_phase"] = sli * 0.35


# --- 3 vases anciens grecs -----------------------------------------------
vases = []
for vi, (vx, vz) in enumerate([(-5, 5), (0, 5), (5, 5)]):
    vp = empty(f"vase_{vi}_p", (vx, 0, vz))
    # base
    smooth_cone(f"vase_{vi}_base", r1=0.20, r2=0.18, depth=0.10, segs=14, loc=(0, 0.05, 0), parent=vp, mat=MAT_VASE_A)
    # body (amphora shape)
    smooth_sphere(f"vase_{vi}_body", r=0.25, segs=20, rings=14, loc=(0, 0.40, 0), parent=vp, mat=MAT_VASE_A, scale=(1.0, 1.5, 1.0))
    # neck
    smooth_cone(f"vase_{vi}_neck", r1=0.12, r2=0.10, depth=0.30, segs=12, loc=(0, 0.85, 0), parent=vp, mat=MAT_VASE_A)
    # 2 handles
    for hk, hz in [(0, 0.18), (1, -0.18)]:
        handle = smooth_cone(f"vase_{vi}_handle_{hk}", r1=0.025, r2=0.025, depth=0.25, segs=6, loc=(0.20, 0.55, hz), parent=vp, mat=MAT_VASE_A)
        handle.rotation_euler = (0, 0, math.radians(35 if hz > 0 else -35))
    # decoration band (dark line)
    smooth_cone(f"vase_{vi}_band", r1=0.26, r2=0.26, depth=0.05, segs=16, loc=(0, 0.55, 0), parent=vp, mat=MAT_VASE_B)
    vp["_phase"] = vi * 0.40
    vases.append(vp)


# --- bouquet fleurs ----------------------------------------------------
bouquet_p = empty("bouquet_p", (-6, 1.5, -4))
# vase
smooth_sphere("bouquet_vase", r=0.30, segs=18, rings=14, loc=(0, 0, 0), parent=bouquet_p, mat=MAT_GOLD, scale=(1.0, 1.2, 1.0))
# 8 stems with flowers
flowers_list = []
for fk in range(8):
    fa = fk * (math.pi * 2 / 8) + random.uniform(-0.2, 0.2)
    fr = 0.10
    fp = empty(f"flower_{fk}_p", (math.cos(fa) * fr, 0.30, math.sin(fa) * fr), parent=bouquet_p)
    flowers_list.append(fp)
    # stem
    smooth_cone(f"flower_{fk}_stem", r1=0.015, r2=0.015, depth=0.45, segs=4, loc=(0, 0.22, 0), parent=fp, mat=MAT_FLOWER_STEM)
    # flower head
    fmat = MAT_FLOWER_A if fk % 2 == 0 else MAT_FLOWER_B
    smooth_sphere(f"flower_{fk}_head", r=0.10, segs=14, rings=10, loc=(0, 0.50, 0), parent=fp, mat=fmat, scale=(1.0, 0.7, 1.0))
    # 5 petals
    for pk in range(5):
        pa = pk * (math.pi * 2 / 5)
        smooth_sphere(f"flower_{fk}_pet_{pk}", r=0.06, segs=10, rings=6, loc=(math.cos(pa) * 0.08, 0.52, math.sin(pa) * 0.08), parent=fp, mat=fmat, scale=(1.4, 0.20, 0.7))


# --- 6 visiteurs silhouettes -------------------------------------------
visitors = []
VISITOR_POSITIONS = [(-2, 0, 1), (2, 0, 1), (-3, 0, -2.5), (3, 0, -2.5), (4, 0, -1), (-4, 0, -1)]
for vi, (vx, vy, vz) in enumerate(VISITOR_POSITIONS):
    vp = empty(f"visitor_{vi}_p", (vx, vy, vz))
    visitors.append(vp)
    # body (oval coat shape)
    smooth_cone(f"visitor_{vi}_body", r1=0.20, r2=0.25, depth=1.4, segs=14, loc=(0, 0.70, 0), parent=vp, mat=MAT_VISITOR if vi % 2 == 0 else MAT_VISITOR_DARK)
    # head
    smooth_sphere(f"visitor_{vi}_head", r=0.16, segs=16, rings=12, loc=(0, 1.55, 0), parent=vp, mat=MAT_VISITOR if vi % 2 == 0 else MAT_VISITOR_DARK, scale=(0.9, 1.1, 0.95))
    vp["_phase"] = vi * 0.5
    vp["_base"] = (vx, vy, vz)


# --- horloge ronde mur ------------------------------------------------
clock_p = empty("clock_p", (0, 6.5, 4.9))
# frame
smooth_cone("clock_frame", r1=0.55, r2=0.55, depth=0.10, segs=22, loc=(0, 0, 0), parent=clock_p, mat=MAT_GOLD_ORNATE)
# inner face
smooth_cone("clock_face_in", r1=0.45, r2=0.45, depth=0.05, segs=22, loc=(0, 0, 0.07), parent=clock_p, mat=MAT_CLOCK_FACE)
# 12 numerals
for n in range(12):
    na = -math.pi / 2 + n * (math.pi * 2 / 12)
    nx = math.cos(na) * 0.36
    ny = math.sin(na) * 0.36
    beveled_cube(f"clock_n_{n}", (0.05, 0.08, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(nx, ny, 0.10), parent=clock_p, mat=MAT_CLOCK_HAND)
# hour hand
hour_p = empty("clock_hour_p", (0, 0, 0.12), parent=clock_p)
beveled_cube("clock_hour", (0.05, 0.25, 0.025), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.08, 0), parent=hour_p, mat=MAT_CLOCK_HAND)
# minute hand
minute_p = empty("clock_minute_p", (0, 0, 0.13), parent=clock_p)
beveled_cube("clock_minute", (0.035, 0.38, 0.025), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.16, 0), parent=minute_p, mat=MAT_CLOCK_HAND)
smooth_sphere("clock_center", r=0.05, segs=12, rings=8, loc=(0, 0, 0.14), parent=clock_p, mat=MAT_GOLD)


# --- balustrade gold (small section) ----------------------------------
for bk in range(5):
    bx = -2 + bk * 1.0
    smooth_cone(f"baluster_{bk}", r1=0.06, r2=0.05, depth=0.80, segs=10, loc=(bx, 0.40, 5), mat=MAT_GOLD)


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

    # 4 spotlights : pulse + sweep
    for si, sp in enumerate(spotlights):
        ph = sp["_phase"]
        ps = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(sp, f, "scale", (ps, ps, ps))
        # sweep angle (housing_p rotation slight)
        housing_obj = bpy.data.objects.get(f"spot_{si}_h_p")
        if housing_obj:
            sweep = math.radians(10 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi))
            base_rot = math.radians(35 + (si % 2) * 20 * (1 if si < 2 else -1))
            kf(housing_obj, f, "rotation_euler", (base_rot, sweep, math.radians(15 if si == 0 else (-15 if si == 1 else 0))))

    # 12 paintings pulse émission (subtle)
    for pd in paintings:
        ph = pd["phase"]
        ps = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        kf(pd["p"], f, "scale", (ps, ps, 1.0))

    # 6 visiteurs walk slow + tête tourne
    for vi, vp in enumerate(visitors):
        bx_, by_, bz_ = vp["_base"]
        ph = vp["_phase"]
        # walking slowly
        new_x = bx_ + 0.5 * math.sin(2 * math.pi * tt * 0.4 + ph)
        new_z = bz_ + 0.3 * math.cos(2 * math.pi * tt * 0.5 + ph)
        kf(vp, f, "location", (new_x, by_, new_z))
        # head turn
        kf(vp, f, "rotation_euler", (0, math.radians(15 * math.sin(2 * math.pi * tt * 0.7 + ph)), 0))

    # clock hands
    hour_ang = tt * 2 * math.pi * 1.0
    minute_ang = tt * 2 * math.pi * 12.0
    kf(hour_p, f, "rotation_euler", (0, 0, -hour_ang))
    kf(minute_p, f, "rotation_euler", (0, 0, -minute_ang))

    # 3 vases rotation léger
    for vsi, vsp in enumerate(vases):
        ph = vsp["_phase"]
        kf(vsp, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 0.3 + ph)), 0))

    # 8 flowers sway gentle (via parent bouquet rotation slight)
    kf(bouquet_p, f, "rotation_euler", (math.radians(3 * math.sin(2 * math.pi * tt * 0.5)), 0, math.radians(2 * math.cos(2 * math.pi * tt * 0.6))))

    # 6 sculptures : subtle bob (effet light playing)
    for sci, sp in enumerate(sculptures):
        kf(sp, f, "rotation_euler", (0, math.radians(3 * math.sin(2 * math.pi * tt * 0.8 + sci * 0.5)), 0))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_art_museum_gallery] wrote {OUT}")
