"""
proc_origami_paper_workshop.py — 178e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Atelier origami avec créations papier :
- table en bois grande
- 20 origamis pliés (grues, dragons, fleurs, étoiles, koi, lapin, papillons, ours, renard, lotus)
- papiers colorés empilés
- ciseaux + règle + outils
- 6 lampes anglepoise émissives
- livres origami
- cadres papier mural
- 4 papillons origami volant
- plante bonsai décorative
- chat regardant
- bibliothèque mur
- 30 papiers volant
- ciel matin

Animations multi-axes simultanées :
- 4 papillons origami flap + orbit
- 30 papiers volant drift 3D + rotate
- 6 lampes pulse
- chat tail wave
- plante sway gentle
- 20 origamis pulse subtle (vie magique)

Sortie : output/3d/pbr_origami_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_origami_proc.glb"))

random.seed(0x0E16AA)


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


def make_origami(name, base_pos, body_mat, scale=1.0, kind="generic"):
    """Build a stylized origami figure (low-poly, faceted)."""
    op = empty(f"origami_{name}_p", base_pos)
    if kind == "crane":
        # body : pyramid + neck + head + 2 wings + tail
        smooth_cone(f"ori_{name}_body", r1=0.18 * scale, r2=0.0, depth=0.30 * scale, segs=4, loc=(0, 0.10, 0), parent=op, mat=body_mat)
        smooth_cone(f"ori_{name}_neck", r1=0.04 * scale, r2=0.03 * scale, depth=0.30 * scale, segs=4, loc=(0.08 * scale, 0.22, 0), parent=op, mat=body_mat)
        smooth_cone(f"ori_{name}_head", r1=0.06 * scale, r2=0.0, depth=0.08 * scale, segs=4, loc=(0.15 * scale, 0.30, 0), parent=op, mat=body_mat)
        # 2 wings
        for wk, wz in [(0, 0.15), (1, -0.15)]:
            wing = smooth_cone(f"ori_{name}_wing_{wk}", r1=0.12 * scale, r2=0.0, depth=0.30 * scale, segs=4, loc=(-0.05 * scale, 0.18, wz * scale), parent=op, mat=body_mat)
            wing.rotation_euler = (0, 0, math.radians(60 if wz > 0 else -60))
        # tail
        smooth_cone(f"ori_{name}_tail", r1=0.08 * scale, r2=0.0, depth=0.15 * scale, segs=4, loc=(-0.15 * scale, 0.15, 0), parent=op, mat=body_mat)
    elif kind == "dragon":
        # elongated body 5 segs + head + wings
        for sg in range(5):
            smooth_sphere(f"ori_{name}_b_{sg}", r=0.10 * scale - sg * 0.01, segs=6, rings=4, loc=(-0.20 * scale + sg * 0.10 * scale, 0.10, 0), parent=op, mat=body_mat)
        # head
        smooth_cone(f"ori_{name}_head", r1=0.10 * scale, r2=0.0, depth=0.15 * scale, segs=4, loc=(0.35 * scale, 0.15, 0), parent=op, mat=body_mat)
        # 2 wings
        for wk, wz in [(0, 0.18), (1, -0.18)]:
            wing = smooth_cone(f"ori_{name}_w_{wk}", r1=0.15 * scale, r2=0.0, depth=0.30 * scale, segs=4, loc=(0.05 * scale, 0.18, wz * scale), parent=op, mat=body_mat)
            wing.rotation_euler = (0, 0, math.radians(45 if wz > 0 else -45))
    elif kind == "flower":
        # 5 petals + center
        for pk in range(5):
            pa = pk * (math.pi * 2 / 5)
            smooth_cone(f"ori_{name}_pet_{pk}", r1=0.10 * scale, r2=0.0, depth=0.15 * scale, segs=4, loc=(math.cos(pa) * 0.12 * scale, 0.10, math.sin(pa) * 0.12 * scale), parent=op, mat=body_mat)
        smooth_sphere(f"ori_{name}_ctr", r=0.06 * scale, segs=6, rings=4, loc=(0, 0.10, 0), parent=op, mat=body_mat)
    elif kind == "star":
        # 5-point star
        for sk in range(5):
            sa = sk * (math.pi * 2 / 5)
            star_seg = smooth_cone(f"ori_{name}_p_{sk}", r1=0.15 * scale, r2=0.0, depth=0.20 * scale, segs=4, loc=(math.cos(sa) * 0.10 * scale, 0.10, math.sin(sa) * 0.10 * scale), parent=op, mat=body_mat)
            star_seg.rotation_euler = (math.radians(90 * math.cos(sa)), 0, math.radians(90 * math.sin(sa)))
    elif kind == "koi":
        # elongated fish + tail + fin
        smooth_sphere(f"ori_{name}_body", r=0.15 * scale, segs=6, rings=4, loc=(0, 0.10, 0), parent=op, mat=body_mat, scale=(1.8, 0.5, 0.85))
        smooth_cone(f"ori_{name}_tail", r1=0.10 * scale, r2=0.0, depth=0.15 * scale, segs=4, loc=(-0.22 * scale, 0.10, 0), parent=op, mat=body_mat)
        # 2 fins
        for fk, fz in [(0, 0.08), (1, -0.08)]:
            smooth_cone(f"ori_{name}_fin_{fk}", r1=0.06 * scale, r2=0.0, depth=0.10 * scale, segs=4, loc=(0, 0.12, fz * scale), parent=op, mat=body_mat)
    elif kind == "rabbit":
        # body + head + 2 ears
        smooth_sphere(f"ori_{name}_body", r=0.18 * scale, segs=6, rings=4, loc=(0, 0.12, 0), parent=op, mat=body_mat, scale=(1.0, 0.85, 1.2))
        smooth_sphere(f"ori_{name}_head", r=0.13 * scale, segs=6, rings=4, loc=(0, 0.30, 0.10), parent=op, mat=body_mat)
        for ek, ez in [(0, 0.05), (1, -0.05)]:
            ear = smooth_cone(f"ori_{name}_ear_{ek}", r1=0.04 * scale, r2=0.0, depth=0.20 * scale, segs=4, loc=(0, 0.45, ez * scale + 0.10), parent=op, mat=body_mat)
            ear.rotation_euler = (math.radians(-10), 0, math.radians(-15 if ez > 0 else 15))
    elif kind == "butterfly":
        # body + 2 wings spread
        smooth_cone(f"ori_{name}_body", r1=0.05 * scale, r2=0.05 * scale, depth=0.20 * scale, segs=4, loc=(0, 0.10, 0), parent=op, mat=body_mat)
        for wk, wz in [(0, 0.15), (1, -0.15)]:
            smooth_cone(f"ori_{name}_w_{wk}", r1=0.18 * scale, r2=0.0, depth=0.25 * scale, segs=4, loc=(0, 0.12, wz * scale), parent=op, mat=body_mat)
    elif kind == "bear":
        # cute body + head + 2 ears
        smooth_sphere(f"ori_{name}_body", r=0.20 * scale, segs=6, rings=4, loc=(0, 0.15, 0), parent=op, mat=body_mat, scale=(1.0, 0.95, 1.0))
        smooth_sphere(f"ori_{name}_head", r=0.15 * scale, segs=6, rings=4, loc=(0, 0.42, 0), parent=op, mat=body_mat)
        for ek, ez in [(0, 0.07), (1, -0.07)]:
            smooth_sphere(f"ori_{name}_ear_{ek}", r=0.05 * scale, segs=4, rings=3, loc=(0, 0.55, ez * scale), parent=op, mat=body_mat)
    elif kind == "fox":
        # body + pointed head + 2 ears
        smooth_sphere(f"ori_{name}_body", r=0.18 * scale, segs=6, rings=4, loc=(0, 0.15, 0), parent=op, mat=body_mat, scale=(1.0, 0.85, 1.2))
        smooth_cone(f"ori_{name}_head", r1=0.10 * scale, r2=0.04 * scale, depth=0.20 * scale, segs=4, loc=(0, 0.35, 0.10), parent=op, mat=body_mat)
        # 2 pointed ears
        for ek, ez in [(0, 0.06), (1, -0.06)]:
            ear = smooth_cone(f"ori_{name}_ear_{ek}", r1=0.04 * scale, r2=0.0, depth=0.12 * scale, segs=4, loc=(0, 0.48, ez * scale + 0.10), parent=op, mat=body_mat)
            ear.rotation_euler = (0, 0, math.radians(-10 if ez > 0 else 10))
        # tail
        smooth_cone(f"ori_{name}_tail", r1=0.08 * scale, r2=0.0, depth=0.20 * scale, segs=4, loc=(-0.20 * scale, 0.18, 0), parent=op, mat=body_mat)
    elif kind == "lotus":
        # multi-layer petals
        for ly in range(3):
            n_pet = 5 + ly
            radius = (0.10 + ly * 0.04) * scale
            for pk in range(n_pet):
                pa = pk * (math.pi * 2 / n_pet)
                smooth_cone(f"ori_{name}_p_{ly}_{pk}", r1=0.06 * scale, r2=0.0, depth=0.15 * scale, segs=4, loc=(math.cos(pa) * radius, 0.10 + ly * 0.03, math.sin(pa) * radius), parent=op, mat=body_mat)
    return op


# --- materials --------------------------------------------------------------
MAT_WALL = make_mat("wall", (0.85, 0.78, 0.65), roughness=0.7, emi=(0.30, 0.28, 0.22), emi_strength=0.3)
MAT_FLOOR = make_mat("floor_wood", (0.50, 0.30, 0.18), roughness=0.55, emi=(0.18, 0.10, 0.05), emi_strength=0.2)
MAT_TABLE = make_mat("table", (0.40, 0.25, 0.12), roughness=0.6)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.06), roughness=0.85)
MAT_PAPER_PINK = make_mat("paper_pink", (0.95, 0.55, 0.75), roughness=0.5, emi=(0.45, 0.20, 0.30), emi_strength=0.6)
MAT_PAPER_RED = make_mat("paper_red", (0.95, 0.25, 0.30), roughness=0.5, emi=(0.45, 0.10, 0.10), emi_strength=0.6)
MAT_PAPER_ORANGE = make_mat("paper_orange", (0.95, 0.55, 0.20), roughness=0.5, emi=(0.45, 0.25, 0.05), emi_strength=0.6)
MAT_PAPER_YELLOW = make_mat("paper_yellow", (0.95, 0.85, 0.30), roughness=0.5, emi=(0.45, 0.40, 0.10), emi_strength=0.6)
MAT_PAPER_GREEN = make_mat("paper_green", (0.30, 0.85, 0.40), roughness=0.5, emi=(0.10, 0.40, 0.15), emi_strength=0.6)
MAT_PAPER_BLUE = make_mat("paper_blue", (0.30, 0.55, 0.95), roughness=0.5, emi=(0.10, 0.25, 0.45), emi_strength=0.6)
MAT_PAPER_PURPLE = make_mat("paper_purple", (0.65, 0.30, 0.95), roughness=0.5, emi=(0.30, 0.10, 0.45), emi_strength=0.6)
MAT_PAPER_WHITE = make_mat("paper_white", (0.95, 0.92, 0.88), roughness=0.5, emi=(0.40, 0.38, 0.35), emi_strength=0.5)
MAT_PAPER_BLACK = make_mat("paper_black", (0.15, 0.12, 0.10), roughness=0.5)
MAT_PAPER_GOLD = make_mat("paper_gold", (0.95, 0.75, 0.25), metallic=0.4, roughness=0.40, emi=(0.45, 0.35, 0.10), emi_strength=0.6)
MAT_METAL = make_mat("metal", (0.50, 0.50, 0.55), metallic=0.85, roughness=0.30)
MAT_BOOK_R = make_mat("book_r", (0.55, 0.15, 0.10), roughness=0.7)
MAT_BOOK_G = make_mat("book_g", (0.15, 0.35, 0.20), roughness=0.7)
MAT_BOOK_B = make_mat("book_b", (0.15, 0.20, 0.50), roughness=0.7)
MAT_LAMP_FRAME = make_mat("lamp_frame", (0.20, 0.15, 0.10), metallic=0.6, roughness=0.4)
MAT_LAMP_GLOW = make_mat("lamp_glow", (1.0, 0.85, 0.55), roughness=0.0, emi=(1.0, 0.85, 0.55), emi_strength=15.0)
MAT_PLANT_STEM = make_mat("plant_stem", (0.25, 0.15, 0.08), roughness=0.7)
MAT_PLANT_LEAF = make_mat("plant_leaf", (0.20, 0.50, 0.20), roughness=0.6, emi=(0.08, 0.20, 0.08), emi_strength=0.3)
MAT_CAT_GRAY = make_mat("cat_gray", (0.30, 0.30, 0.30), roughness=0.6)
MAT_CAT_EYE = make_mat("cat_eye", (0.95, 0.85, 0.30), roughness=0.0, emi=(0.95, 0.85, 0.30), emi_strength=10.0)
MAT_RUG = make_mat("rug", (0.55, 0.30, 0.30), roughness=0.85, emi=(0.18, 0.08, 0.08), emi_strength=0.3)
MAT_WINDOW = make_mat("window", (0.95, 0.85, 0.65), roughness=0.0, emi=(0.95, 0.85, 0.65), emi_strength=8.0)


# --- backdrop : workshop ----------------------------------------------------
back_wall = beveled_cube("back_wall", (14, 0.2, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 4, -4), mat=MAT_WALL)
side_wall_L = beveled_cube("side_wall_L", (0.2, 8, 10), bevel_offset=0.05, bevel_segments=2, loc=(-7, 4, 0), mat=MAT_WALL)
side_wall_R = beveled_cube("side_wall_R", (0.2, 8, 10), bevel_offset=0.05, bevel_segments=2, loc=(7, 4, 0), mat=MAT_WALL)
floor = beveled_cube("floor", (14, 0.1, 10), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_FLOOR)
# rug
beveled_cube("rug", (5, 0.04, 3), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.02, 1), mat=MAT_RUG)

# 2 windows
for wi, wx in [(0, -3), (1, 3)]:
    win_p = empty(f"window_{wi}_p", (wx, 5, -3.85))
    beveled_cube(f"window_{wi}_frame", (1.8, 2.5, 0.10), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=win_p, mat=MAT_WOOD_DARK)
    beveled_cube(f"window_{wi}_glow", (1.6, 2.3, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.07), parent=win_p, mat=MAT_WINDOW)


# --- TABLE EN BOIS centrale ----------------------------------------------
table_p = empty("table_p", (0, 0, 0.5))
beveled_cube("table_top", (4.5, 0.10, 2.5), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.0, 0), parent=table_p, mat=MAT_TABLE)
for lx, lz in [(-2.0, -1.05), (2.0, -1.05), (-2.0, 1.05), (2.0, 1.05)]:
    smooth_cone(f"table_leg_{lx}_{lz}", r1=0.08, r2=0.07, depth=1.0, segs=10, loc=(lx, 0.50, lz), parent=table_p, mat=MAT_WOOD_DARK)


# --- 20 ORIGAMI sur table -----------------------------------------------
ORIGAMI_TYPES = ["crane", "dragon", "flower", "star", "koi", "rabbit", "butterfly", "bear", "fox", "lotus"]
PAPER_MATS = [MAT_PAPER_PINK, MAT_PAPER_RED, MAT_PAPER_ORANGE, MAT_PAPER_YELLOW, MAT_PAPER_GREEN, MAT_PAPER_BLUE, MAT_PAPER_PURPLE, MAT_PAPER_WHITE, MAT_PAPER_BLACK, MAT_PAPER_GOLD]
origami_table = []
for oi in range(20):
    kind = ORIGAMI_TYPES[oi % len(ORIGAMI_TYPES)]
    mat = PAPER_MATS[oi % len(PAPER_MATS)]
    # distribute on table (4 rows × 5 cols)
    row = oi // 5
    col = oi % 5
    ox = -1.8 + col * 0.9
    oz = -0.9 + row * 0.6
    op = make_origami(f"tbl_{oi}_{kind}", (ox, 1.10, oz), mat, scale=0.7, kind=kind)
    op["_phase"] = oi * 0.20
    origami_table.append(op)


# --- PAPIERS COLORÉS empilés ---------------------------------------------
for stk in range(8):
    sx = -2.3 + (stk % 4) * 0.20
    sz = -0.95 + (stk // 4) * 0.20
    pmat = PAPER_MATS[stk % len(PAPER_MATS)]
    beveled_cube(f"paper_stack_{stk}", (0.30, 0.02, 0.30), bevel_offset=0.01, bevel_segments=2, loc=(sx, 1.06, sz), mat=pmat)


# --- CISEAUX + RÈGLE outils sur table ----------------------------------
# ciseaux (2 blades + 2 anneaux)
scissors_p = empty("scissors_p", (2, 1.10, 0))
scissors_p.rotation_euler = (0, 0, math.radians(15))
# blades
for bk, bz in [(0, -0.04), (1, 0.04)]:
    blade = smooth_cone(f"scissors_blade_{bk}", r1=0.025, r2=0.0, depth=0.35, segs=6, loc=(0.10, 0.02, bz), parent=scissors_p, mat=MAT_METAL)
# handle loops
for hk, hx in [(0, -0.20), (1, -0.20)]:
    smooth_cone(f"scissors_loop_{hk}", r1=0.07, r2=0.06, depth=0.05, segs=10, loc=(hx, 0.02, -0.04 + hk * 0.08), parent=scissors_p, mat=MAT_LAMP_FRAME)
# rivet
smooth_sphere("scissors_rivet", r=0.03, segs=10, rings=8, loc=(0, 0.025, 0), parent=scissors_p, mat=MAT_LAMP_FRAME)

# règle
beveled_cube("ruler", (1.5, 0.02, 0.15), bevel_offset=0.01, bevel_segments=2, loc=(1.5, 1.07, 0.5), mat=MAT_PAPER_WHITE)


# --- 6 LAMPES ANGLEPOISE --------------------------------------------
lamps = []
LAMP_POSITIONS = [(-2.5, 1.0, 0.8), (2.5, 1.0, 0.8), (-3.5, 0, 2), (3.5, 0, 2), (-3.5, 0, -2), (3.5, 0, -2)]
for li, (lx, ly, lz) in enumerate(LAMP_POSITIONS):
    lp = empty(f"lamp_{li}_p", (lx, ly, lz))
    lamps.append(lp)
    # base
    smooth_cone(f"lamp_{li}_base", r1=0.15, r2=0.12, depth=0.06, segs=14, loc=(0, 0.03, 0), parent=lp, mat=MAT_LAMP_FRAME)
    # vertical pole
    smooth_cone(f"lamp_{li}_pole1", r1=0.03, r2=0.03, depth=0.85, segs=8, loc=(0, 0.50, 0), parent=lp, mat=MAT_LAMP_FRAME)
    # joint sphere
    smooth_sphere(f"lamp_{li}_joint1", r=0.07, segs=12, rings=8, loc=(0, 0.95, 0), parent=lp, mat=MAT_LAMP_FRAME)
    # bent arm
    arm = smooth_cone(f"lamp_{li}_arm", r1=0.03, r2=0.03, depth=0.70, segs=8, loc=(0.20, 1.15, 0), parent=lp, mat=MAT_LAMP_FRAME)
    arm.rotation_euler = (0, 0, math.radians(-50))
    # second joint
    smooth_sphere(f"lamp_{li}_joint2", r=0.06, segs=12, rings=8, loc=(0.50, 1.35, 0), parent=lp, mat=MAT_LAMP_FRAME)
    # shade
    smooth_cone(f"lamp_{li}_shade", r1=0.20, r2=0.10, depth=0.20, segs=14, loc=(0.65, 1.30, 0), parent=lp, mat=MAT_LAMP_FRAME)
    sp = bpy.data.objects.get(f"lamp_{li}_shade")
    if sp:
        sp.rotation_euler = (0, 0, math.radians(-20))
    # glow inside shade
    glow = smooth_sphere(f"lamp_{li}_glow", r=0.12, segs=14, rings=10, loc=(0.78, 1.20, 0), parent=lp, mat=MAT_LAMP_GLOW)
    lp["_glow"] = glow
    lp["_phase"] = li * 0.25


# --- BIBLIOTHÈQUE bookshelf ----------------------------------------------
bookshelf_p = empty("bookshelf", (-6, 0, 0))
bookshelf_p.rotation_euler = (0, math.radians(90), 0)
# frame
beveled_cube("bs_frame", (3.0, 5.0, 0.40), bevel_offset=0.05, bevel_segments=2, loc=(0, 2.5, 0), parent=bookshelf_p, mat=MAT_WOOD_DARK)
# 4 shelves + books
for sh in range(4):
    beveled_cube(f"bs_shelf_{sh}", (2.8, 0.06, 0.35), bevel_offset=0.02, bevel_segments=2, loc=(0, 1.0 + sh * 1.0, 0.15), parent=bookshelf_p, mat=MAT_TABLE)
    # ~12 books per shelf
    for bk in range(12):
        bx = -1.3 + bk * 0.22 + random.uniform(-0.03, 0.03)
        bh = random.uniform(0.55, 0.80)
        bw = random.uniform(0.13, 0.18)
        bd = random.uniform(0.28, 0.35)
        bmat = [MAT_BOOK_R, MAT_BOOK_G, MAT_BOOK_B][bk % 3]
        beveled_cube(f"bs_book_{sh}_{bk}", (bw, bh, bd), bevel_offset=0.01, bevel_segments=2, loc=(bx, 1.05 + sh * 1.0 + bh / 2, 0.15 + bd / 2 - 0.10), parent=bookshelf_p, mat=bmat)


# --- 4 CADRES PAPIER mural -----------------------------------------------
for fk, (fx, fy, fz) in enumerate([(-3, 5, -3.85), (-1, 5.5, -3.85), (1, 5.5, -3.85), (3, 5, -3.85)]):
    fp = empty(f"frame_{fk}_p", (fx, fy, fz))
    beveled_cube(f"frame_{fk}_outer", (0.85, 1.0, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=fp, mat=MAT_WOOD_DARK)
    pmat = PAPER_MATS[fk % len(PAPER_MATS)]
    beveled_cube(f"frame_{fk}_pic", (0.70, 0.85, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0.04), parent=fp, mat=pmat)


# --- 4 PAPILLONS ORIGAMI VOLANT -----------------------------------------
flying_butterflies = []
for bk in range(4):
    a = bk * (math.pi * 2 / 4) + 0.5
    r = random.uniform(2.5, 4.0)
    y = random.uniform(3, 6)
    bmat = PAPER_MATS[bk % len(PAPER_MATS)]
    bp = empty(f"flybut_{bk}_p", (math.cos(a) * r, y, math.sin(a) * r))
    flying_butterflies.append({"p": bp, "a": a, "r": r, "y": y, "phase": bk * 0.30})
    # small body
    smooth_cone(f"flybut_{bk}_body", r1=0.04, r2=0.04, depth=0.20, segs=4, loc=(0, 0, 0), parent=bp, mat=MAT_PAPER_BLACK)
    # 2 wings
    wL = empty(f"flybut_{bk}_wL", (0, 0, 0.04), parent=bp)
    wR = empty(f"flybut_{bk}_wR", (0, 0, -0.04), parent=bp)
    smooth_cone(f"flybut_{bk}_wL_b", r1=0.15, r2=0.0, depth=0.25, segs=4, loc=(0, 0, 0.10), parent=wL, mat=bmat)
    smooth_cone(f"flybut_{bk}_wR_b", r1=0.15, r2=0.0, depth=0.25, segs=4, loc=(0, 0, -0.10), parent=wR, mat=bmat)
    flying_butterflies[bk]["wL"] = wL
    flying_butterflies[bk]["wR"] = wR


# --- BONSAI décoratif ------------------------------------------------
bonsai_p = empty("bonsai", (3.5, 1.10, -0.8))
# pot
smooth_cone("bonsai_pot", r1=0.25, r2=0.20, depth=0.15, segs=14, loc=(0, 0.08, 0), parent=bonsai_p, mat=MAT_PAPER_RED)
# trunk twisted (3 segs)
cur = bonsai_p
for sg in range(3):
    seg_p = empty(f"bonsai_seg_{sg}", (0, 0.25, 0), parent=cur)
    seg_p.rotation_euler = (math.radians(random.uniform(-15, 15)), 0, math.radians(random.uniform(-15, 15)))
    smooth_cone(f"bonsai_t_{sg}", r1=0.05 - sg * 0.005, r2=0.04 - sg * 0.005, depth=0.20, segs=8, loc=(0, 0.10, 0), parent=seg_p, mat=MAT_PLANT_STEM)
    cur = seg_p
# leaves clusters
for lk in range(6):
    la = lk * (math.pi * 2 / 6)
    smooth_sphere(f"bonsai_leaf_{lk}", r=0.10, segs=14, rings=8, loc=(math.cos(la) * 0.15, 0.10, math.sin(la) * 0.15), parent=cur, mat=MAT_PLANT_LEAF, scale=(1.0, 0.5, 1.0))


# --- CHAT GRIS regardant ---------------------------------------------
cat_p = empty("cat_p", (-3.5, 0, -1.5))
# body curled
smooth_sphere("cat_body", r=0.22, segs=18, rings=12, loc=(0, 0.20, 0), parent=cat_p, mat=MAT_CAT_GRAY, scale=(1.4, 0.95, 1.1))
# head
smooth_sphere("cat_head", r=0.16, segs=16, rings=12, loc=(0.20, 0.30, 0), parent=cat_p, mat=MAT_CAT_GRAY)
# 2 ears
for ek, ez in [("L", 0.07), ("R", -0.07)]:
    smooth_cone(f"cat_ear_{ek}", r1=0.05, r2=0.0, depth=0.10, segs=8, loc=(0.20, 0.45, ez), parent=cat_p, mat=MAT_CAT_GRAY)
# 2 yellow eyes
for ek, ez in [("L", 0.05), ("R", -0.05)]:
    smooth_sphere(f"cat_eye_{ek}", r=0.028, segs=10, rings=6, loc=(0.30, 0.32, ez), parent=cat_p, mat=MAT_CAT_EYE)
# tail curled
tail_p = empty("cat_tail_p", (-0.18, 0.22, 0), parent=cat_p)
for tk in range(4):
    smooth_sphere(f"cat_tail_{tk}", r=0.045, segs=10, rings=6, loc=(-0.10 - tk * 0.08, 0.05 + tk * 0.05, 0), parent=tail_p, mat=MAT_CAT_GRAY)


# --- 30 PAPIERS volant drift 3D ---------------------------------
flying_papers = []
for pk in range(30):
    px = random.uniform(-6, 6)
    py = random.uniform(2, 7)
    pz = random.uniform(-3, 4)
    pmat = PAPER_MATS[pk % len(PAPER_MATS)]
    # small flat paper square
    pp = beveled_cube(f"flypaper_{pk}", (0.18, 0.02, 0.18), bevel_offset=0.01, bevel_segments=2, loc=(px, py, pz), mat=pmat)
    pp["_base"] = (px, py, pz)
    pp["_phase"] = pk * 0.15
    flying_papers.append(pp)


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

    # 20 origami table : subtle pulse + rotate Y (life)
    for oi, op in enumerate(origami_table):
        ph = op["_phase"]
        ps = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(op, f, "scale", (ps, ps, ps))
        kf(op, f, "rotation_euler", (0, math.radians(8 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)), 0))

    # 6 lamps pulse
    for ld in lamps:
        ph = ld["_phase"]
        ps = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(ld["_glow"], f, "scale", (ps, ps, ps))

    # 4 flying butterflies : orbit + flap
    for fb in flying_butterflies:
        ang = fb["a"] + tt * 2 * math.pi * 0.5
        bx_ = math.cos(ang) * fb["r"]
        bz_ = math.sin(ang) * fb["r"]
        by_ = fb["y"] + 0.5 * math.sin(2 * math.pi * tt * 1.5 + fb["phase"])
        kf(fb["p"], f, "location", (bx_, by_, bz_))
        kf(fb["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(60) * math.sin(2 * math.pi * tt * 10 + fb["phase"])
        kf(fb["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(fb["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 30 flying papers drift 3D + rotate
    for pp in flying_papers:
        bx_, by_, bz_ = pp["_base"]
        ph = pp["_phase"]
        nx = bx_ + 0.6 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        ny = by_ + 0.5 * math.cos(2 * math.pi * tt * 0.8 + ph * math.pi)
        nz = bz_ + 0.5 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(pp, f, "location", (nx, ny, nz))
        kf(pp, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # bonsai gentle sway
    kf(bonsai_p, f, "rotation_euler", (math.radians(2 * math.sin(2 * math.pi * tt * 0.7)), 0, math.radians(2 * math.cos(2 * math.pi * tt * 0.8))))

    # cat tail wave
    kf(tail_p, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 1.5)), math.radians(15 * math.cos(2 * math.pi * tt * 1.2))))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_origami_paper_workshop] wrote {OUT}")
