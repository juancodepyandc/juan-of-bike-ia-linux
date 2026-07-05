"""
proc_steampunk_submarine_interior.py — 173e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Intérieur cockpit sous-marin steampunk (Nautilus-like) :
- fenêtre arrière océan (porthole géant + 30 poissons visible)
- 4 panneaux contrôles avec 30 gauges + boutons émissifs
- grand volant cuivre (steering wheel)
- levier vitesse
- horloge avec 3 aiguilles
- compass nautique
- tuyaux cuivre interconnectés
- masque oxygène pendant
- 6 lampes edison
- journal navigation ouvert
- table en bois + chaise capitaine
- 4 portholes émissifs latéraux
- drapeau navire
- crâne marin sur étagère
- sextant brass
- 8 fioles
- ciel sous-marin par fenêtre

Animations multi-axes simultanées :
- 3 aiguilles horloge (heure/minute/seconde)
- volant rotation lente capitaine
- 30 gauges pulse + ticking
- 6 lampes edison pulse différentielles
- journal pages ondulent
- compass pivot N/E/W/S
- 30 poissons fenêtre swim
- portholes pulse

Sortie : output/3d/pbr_subcockpit_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_subcockpit_proc.glb"))

random.seed(0x5B4CCC)


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
MAT_HULL = make_mat("hull", (0.18, 0.12, 0.08), roughness=0.85)
MAT_HULL_BRIGHT = make_mat("hull_bright", (0.30, 0.20, 0.12), roughness=0.7)
MAT_FLOOR = make_mat("floor", (0.25, 0.15, 0.08), roughness=0.85)
MAT_BRASS = make_mat("brass", (0.90, 0.70, 0.30), metallic=0.95, roughness=0.20, emi=(0.40, 0.30, 0.10), emi_strength=0.5)
MAT_BRASS_BRIGHT = make_mat("brass_bright", (1.0, 0.85, 0.40), metallic=0.95, roughness=0.15, emi=(0.55, 0.40, 0.15), emi_strength=0.8)
MAT_BRASS_DARK = make_mat("brass_dark", (0.55, 0.40, 0.18), metallic=0.85, roughness=0.45)
MAT_COPPER = make_mat("copper", (0.85, 0.50, 0.30), metallic=0.85, roughness=0.30, emi=(0.30, 0.18, 0.12), emi_strength=0.4)
MAT_IRON = make_mat("iron", (0.30, 0.28, 0.28), metallic=0.80, roughness=0.50)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.06), roughness=0.85)
MAT_WOOD_RED = make_mat("wood_red", (0.45, 0.20, 0.12), roughness=0.7)
MAT_GLASS = make_mat("glass", (0.85, 0.95, 1.0), roughness=0.05, alpha=0.40, emi=(0.40, 0.55, 0.65), emi_strength=1.5)
MAT_OCEAN_VIEW = make_mat("ocean_view", (0.15, 0.40, 0.60), roughness=0.20, alpha=0.80, emi=(0.10, 0.30, 0.55), emi_strength=2.5)
MAT_EDISON = make_mat("edison", (1.0, 0.65, 0.20), roughness=0.0, emi=(1.0, 0.65, 0.20), emi_strength=14.0)
MAT_GAUGE_FACE = make_mat("gauge_face", (0.95, 0.88, 0.65), roughness=0.40, emi=(0.45, 0.40, 0.30), emi_strength=0.8)
MAT_GAUGE_GREEN = make_mat("gauge_green", (0.30, 0.95, 0.40), roughness=0.0, emi=(0.30, 0.95, 0.40), emi_strength=9.0)
MAT_GAUGE_RED = make_mat("gauge_red", (0.95, 0.30, 0.30), roughness=0.0, emi=(0.95, 0.30, 0.30), emi_strength=9.0)
MAT_GAUGE_BLUE = make_mat("gauge_blue", (0.30, 0.55, 0.95), roughness=0.0, emi=(0.30, 0.55, 0.95), emi_strength=9.0)
MAT_GAUGE_AMBER = make_mat("gauge_amber", (0.95, 0.65, 0.20), roughness=0.0, emi=(0.95, 0.65, 0.20), emi_strength=9.0)
MAT_NEEDLE = make_mat("needle", (0.15, 0.10, 0.05), metallic=0.50, roughness=0.40)
MAT_LEATHER = make_mat("leather", (0.30, 0.15, 0.05), roughness=0.85)
MAT_PARCHMENT = make_mat("parchment", (0.85, 0.75, 0.55), roughness=0.7, emi=(0.30, 0.25, 0.18), emi_strength=0.4)
MAT_BONE = make_mat("bone", (0.85, 0.82, 0.75), roughness=0.5, emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_FISH_A = make_mat("fish_A", (0.95, 0.55, 0.20), roughness=0.4, emi=(0.45, 0.25, 0.10), emi_strength=0.6)
MAT_FISH_B = make_mat("fish_B", (0.30, 0.55, 0.95), roughness=0.4, emi=(0.15, 0.25, 0.55), emi_strength=0.6)
MAT_RUBY = make_mat("ruby", (1.0, 0.15, 0.30), roughness=0.05, emi=(1.0, 0.15, 0.30), emi_strength=6.0)
MAT_POTION_R = make_mat("potion_red", (0.95, 0.20, 0.30), roughness=0.10, alpha=0.85, emi=(0.95, 0.20, 0.30), emi_strength=8.0)
MAT_POTION_G = make_mat("potion_green", (0.30, 0.95, 0.40), roughness=0.10, alpha=0.85, emi=(0.30, 0.95, 0.40), emi_strength=8.0)
MAT_POTION_B = make_mat("potion_blue", (0.30, 0.55, 0.95), roughness=0.10, alpha=0.85, emi=(0.30, 0.55, 0.95), emi_strength=8.0)
MAT_POTION_BOTTLE = make_mat("potion_bottle", (0.85, 0.90, 0.95), roughness=0.20, alpha=0.55, emi=(0.30, 0.35, 0.40), emi_strength=0.5)
MAT_FLAG = make_mat("flag", (0.75, 0.15, 0.10), roughness=0.7, emi=(0.30, 0.05, 0.05), emi_strength=0.4)


# --- backdrop : interior hull -------------------------------------------
# back wall (curved)
back_wall = beveled_cube("back_wall", (12, 0.3, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 4, -4), mat=MAT_HULL)
# floor
floor = beveled_cube("floor", (12, 0.2, 10), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_FLOOR)
# ceiling
ceiling = beveled_cube("ceiling", (12, 0.2, 10), bevel_offset=0.05, bevel_segments=2, loc=(0, 8.10, 0), mat=MAT_HULL_BRIGHT)
# side walls
side_wall_L = beveled_cube("side_wall_L", (0.3, 8, 10), bevel_offset=0.05, bevel_segments=2, loc=(-6, 4, 0), mat=MAT_HULL)
side_wall_R = beveled_cube("side_wall_R", (0.3, 8, 10), bevel_offset=0.05, bevel_segments=2, loc=(6, 4, 0), mat=MAT_HULL)


# --- LARGE BACK PORTHOLE (ocean view window) ----------------------------
porthole_p = empty("porthole_p", (0, 4.5, -3.85))
# frame ring (large torus-like via multiple cone discs)
frame_ring = smooth_cone("porthole_frame", r1=2.3, r2=2.3, depth=0.20, segs=32, loc=(0, 0, 0), parent=porthole_p, mat=MAT_BRASS_DARK)
# inner ring (smaller, recessed)
inner_ring = smooth_cone("porthole_inner_ring", r1=2.1, r2=2.1, depth=0.10, segs=32, loc=(0, 0, 0.05), parent=porthole_p, mat=MAT_BRASS_BRIGHT)
# glass view
glass = smooth_cone("porthole_glass", r1=1.95, r2=1.95, depth=0.05, segs=32, loc=(0, 0, 0.10), parent=porthole_p, mat=MAT_GLASS)
# ocean visible beyond
ocean_view = smooth_cone("ocean_view", r1=1.90, r2=1.90, depth=0.04, segs=32, loc=(0, 0, 0.13), parent=porthole_p, mat=MAT_OCEAN_VIEW)
# 8 bolts around frame
for bk in range(8):
    ba = bk * (math.pi * 2 / 8)
    bx = math.cos(ba) * 2.20
    by = math.sin(ba) * 2.20
    smooth_sphere(f"porthole_bolt_{bk}", r=0.08, segs=12, rings=8, loc=(bx, by, 0.15), parent=porthole_p, mat=MAT_BRASS_BRIGHT)


# --- 30 POISSONS visible derrière fenêtre ---------------------------
fish_visible = []
for fk in range(30):
    a = fk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(0.3, 1.7)
    fx = math.cos(a) * r
    fy = 4.5 + math.sin(a) * r * 0.85
    fp = empty(f"fish_v_{fk}_p", (fx, fy, -3.78))
    fmat = MAT_FISH_A if fk % 2 == 0 else MAT_FISH_B
    smooth_sphere(f"fish_v_{fk}_b", r=0.08, segs=10, rings=6, loc=(0, 0, 0), parent=fp, mat=fmat, scale=(1.6, 0.85, 0.5))
    smooth_sphere(f"fish_v_{fk}_t", r=0.05, segs=8, rings=6, loc=(-0.10, 0, 0), parent=fp, mat=fmat, scale=(0.5, 1.2, 0.1))
    fish_visible.append({"p": fp, "a0": a, "r": r, "phase": fk * 0.15})


# --- 4 PANNEAUX CONTRÔLES avec gauges --------------------------------
# 2 panneaux gauche + 2 panneaux droite
gauges = []
panel_positions = [(-4, 3.5, 1.5, -90), (-4, 3.5, -1.5, -90), (4, 3.5, 1.5, 90), (4, 3.5, -1.5, 90)]
for pi, (px, py, pz, prot) in enumerate(panel_positions):
    pp = empty(f"panel_{pi}_p", (px, py, pz))
    pp.rotation_euler = (0, math.radians(prot), 0)
    # panel base
    panel = beveled_cube(f"panel_{pi}_base", (0.30, 2.0, 1.5), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=pp, mat=MAT_WOOD_RED)
    # 8 gauges per panel (4x2 grid)
    for gk in range(8):
        gx_off = -0.50 + (gk % 4) * 0.30
        gy_off = -0.40 + (gk // 4) * 0.45
        gp = empty(f"gauge_{pi}_{gk}_p", (0.18, gy_off, gx_off), parent=pp)
        gp.rotation_euler = (0, math.radians(90), 0)
        # frame
        smooth_cone(f"gauge_{pi}_{gk}_fr", r1=0.13, r2=0.13, depth=0.05, segs=14, loc=(0, 0, 0), parent=gp, mat=MAT_BRASS_DARK)
        # face
        smooth_cone(f"gauge_{pi}_{gk}_face", r1=0.11, r2=0.11, depth=0.04, segs=14, loc=(0, 0, 0.03), parent=gp, mat=MAT_GAUGE_FACE)
        # needle
        needle_p = empty(f"gauge_{pi}_{gk}_n_p", (0, 0, 0.07), parent=gp)
        beveled_cube(f"gauge_{pi}_{gk}_n", (0.03, 0.08, 0.015), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.04, 0), parent=needle_p, mat=MAT_NEEDLE)
        # glow indicator (small émissif)
        glow_mats = [MAT_GAUGE_GREEN, MAT_GAUGE_RED, MAT_GAUGE_BLUE, MAT_GAUGE_AMBER]
        glow_mat = glow_mats[(pi * 8 + gk) % 4]
        smooth_sphere(f"gauge_{pi}_{gk}_glow", r=0.025, segs=10, rings=6, loc=(0.08, 0, 0.08), parent=gp, mat=glow_mat)
        gauges.append({"needle": needle_p, "glow_mat": glow_mat, "phase": (pi * 8 + gk) * 0.12})


# --- GRAND VOLANT CUIVRE -----------------------------------------------
wheel_p = empty("wheel_p", (0, 3.5, 3))
wheel_p.rotation_euler = (math.radians(90), 0, 0)
# outer ring
smooth_cone("wheel_ring", r1=0.85, r2=0.85, depth=0.10, segs=22, loc=(0, 0, 0), parent=wheel_p, mat=MAT_BRASS)
# 8 spokes
for sk in range(8):
    sa = sk * (math.pi * 2 / 8)
    beveled_cube(f"wheel_spoke_{sk}", (0.05, 0.75, 0.05), bevel_offset=0.01, bevel_segments=2, loc=(math.cos(sa) * 0.40, math.sin(sa) * 0.40, 0), parent=wheel_p, mat=MAT_BRASS)
    bp = bpy.data.objects.get(f"wheel_spoke_{sk}")
    if bp:
        bp.rotation_euler = (0, 0, sa)
# center hub
smooth_sphere("wheel_hub", r=0.18, segs=18, rings=12, loc=(0, 0, 0), parent=wheel_p, mat=MAT_BRASS_BRIGHT)
# 8 handles on rim
for hk in range(8):
    ha = hk * (math.pi * 2 / 8) + math.pi / 8
    smooth_cone(f"wheel_handle_{hk}", r1=0.05, r2=0.04, depth=0.25, segs=10, loc=(math.cos(ha) * 0.95, math.sin(ha) * 0.95, 0), parent=wheel_p, mat=MAT_WOOD_DARK)


# --- LEVIER VITESSE ----------------------------------------------------
lever_p = empty("lever_p", (1.5, 2, 3))
# base
smooth_cone("lever_base", r1=0.20, r2=0.18, depth=0.10, segs=14, loc=(0, 0.05, 0), parent=lever_p, mat=MAT_BRASS_DARK)
# stick
smooth_cone("lever_stick", r1=0.04, r2=0.04, depth=0.80, segs=10, loc=(0, 0.50, 0), parent=lever_p, mat=MAT_IRON)
lever_p.rotation_euler = (0, 0, math.radians(15))
# handle ball
smooth_sphere("lever_handle", r=0.10, segs=14, rings=10, loc=(0, 0.95, 0), parent=lever_p, mat=MAT_RUBY)


# --- HORLOGE avec 3 aiguilles ----------------------------------------
clock_p = empty("clock_p", (-2.5, 5, -3.85))
# frame
smooth_cone("clock_frame", r1=0.50, r2=0.50, depth=0.10, segs=22, loc=(0, 0, 0), parent=clock_p, mat=MAT_BRASS)
# face
smooth_cone("clock_face", r1=0.42, r2=0.42, depth=0.05, segs=22, loc=(0, 0, 0.06), parent=clock_p, mat=MAT_GAUGE_FACE)
# 12 numerals
for n in range(12):
    na = -math.pi / 2 + n * (math.pi * 2 / 12)
    nx = math.cos(na) * 0.32
    ny = math.sin(na) * 0.32
    beveled_cube(f"clock_n_{n}", (0.04, 0.07, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(nx, ny, 0.09), parent=clock_p, mat=MAT_NEEDLE)
# hour hand
hour_p = empty("hour_p", (0, 0, 0.11), parent=clock_p)
beveled_cube("hour", (0.04, 0.22, 0.020), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.08, 0), parent=hour_p, mat=MAT_NEEDLE)
# minute hand
minute_p = empty("minute_p", (0, 0, 0.12), parent=clock_p)
beveled_cube("minute", (0.03, 0.34, 0.020), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.14, 0), parent=minute_p, mat=MAT_NEEDLE)
# second hand
second_p = empty("second_p", (0, 0, 0.13), parent=clock_p)
beveled_cube("second", (0.02, 0.36, 0.015), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.15, 0), parent=second_p, mat=MAT_BRASS_BRIGHT)


# --- COMPASS nautique ---------------------------------------------------
compass_p = empty("compass_p", (2.5, 5, -3.85))
# frame
smooth_cone("compass_frame", r1=0.45, r2=0.45, depth=0.10, segs=22, loc=(0, 0, 0), parent=compass_p, mat=MAT_BRASS)
# face
smooth_cone("compass_face", r1=0.38, r2=0.38, depth=0.05, segs=22, loc=(0, 0, 0.06), parent=compass_p, mat=MAT_GAUGE_FACE)
# N/E/S/W markings (4 cones)
for ck in range(4):
    ca = -math.pi / 2 + ck * (math.pi / 2)
    cx = math.cos(ca) * 0.28
    cy = math.sin(ca) * 0.28
    smooth_cone(f"compass_dir_{ck}", r1=0.03, r2=0.0, depth=0.10, segs=6, loc=(cx, cy, 0.10), parent=compass_p, mat=MAT_NEEDLE)
# needle (pointing N)
needle_p = empty("compass_needle_p", (0, 0, 0.13), parent=compass_p)
beveled_cube("compass_needle_red", (0.02, 0.25, 0.015), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.10, 0), parent=needle_p, mat=MAT_GAUGE_RED)
beveled_cube("compass_needle_white", (0.02, 0.25, 0.015), bevel_offset=0.01, bevel_segments=2, loc=(0, -0.10, 0), parent=needle_p, mat=MAT_GAUGE_FACE)


# --- 6 LAMPES EDISON --------------------------------------------------
edison_lamps = []
EDISON_POS = [(-4, 7, 2), (0, 7.5, 2), (4, 7, 2), (-4, 7, -2), (0, 7.5, -2), (4, 7, -2)]
for li, (lx, ly, lz) in enumerate(EDISON_POS):
    lp = empty(f"edison_{li}_p", (lx, ly, lz))
    edison_lamps.append(lp)
    # chain
    smooth_cone(f"edison_{li}_chain", r1=0.015, r2=0.015, depth=1.0, segs=4, loc=(0, 0.55, 0), parent=lp, mat=MAT_BRASS_DARK)
    # glass envelope
    smooth_sphere(f"edison_{li}_glass", r=0.15, segs=14, rings=10, loc=(0, 0, 0), parent=lp, mat=MAT_GLASS, scale=(1.0, 1.4, 1.0))
    # filament
    fil = smooth_sphere(f"edison_{li}_fil", r=0.07, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_EDISON)
    # socket
    smooth_cone(f"edison_{li}_socket", r1=0.08, r2=0.07, depth=0.10, segs=10, loc=(0, 0.18, 0), parent=lp, mat=MAT_BRASS_DARK)
    lp["_phase"] = li * 0.30
    lp["_fil"] = fil


# --- JOURNAL DE NAVIGATION (ouvert sur table) -----------------------------
table_p = empty("table_p", (-3.5, 2, 2))
beveled_cube("table_top", (1.5, 0.10, 1.0), bevel_offset=0.03, bevel_segments=2, loc=(0, 1.5, 0), parent=table_p, mat=MAT_WOOD_RED)
for lx, lz in [(-0.65, -0.4), (0.65, -0.4), (-0.65, 0.4), (0.65, 0.4)]:
    smooth_cone(f"table_leg_{lx}_{lz}", r1=0.05, r2=0.04, depth=1.5, segs=8, loc=(lx, 0.75, lz), parent=table_p, mat=MAT_WOOD_DARK)

# journal
journal_p = empty("journal_p", (0, 1.60, 0), parent=table_p)
# cover left page
left_page = beveled_cube("journal_left", (0.50, 0.04, 0.40), bevel_offset=0.02, bevel_segments=2, loc=(-0.26, 0.02, 0), parent=journal_p, mat=MAT_PARCHMENT)
# right page (the one that turns)
right_page = beveled_cube("journal_right", (0.50, 0.04, 0.40), bevel_offset=0.02, bevel_segments=2, loc=(0.26, 0.02, 0), parent=journal_p, mat=MAT_PARCHMENT)
# spine
beveled_cube("journal_spine", (0.06, 0.08, 0.40), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.05, 0), parent=journal_p, mat=MAT_LEATHER)


# --- 4 PORTHOLES latéraux émissifs ------------------------------------
side_portholes = []
SIDE_PORTHOLES = [(-5.85, 4, 1.5, -90), (-5.85, 4, -1.5, -90), (5.85, 4, 1.5, 90), (5.85, 4, -1.5, 90)]
for spi, (px, py, pz, prot) in enumerate(SIDE_PORTHOLES):
    sp = empty(f"sideport_{spi}_p", (px, py, pz))
    sp.rotation_euler = (0, math.radians(prot), 0)
    # frame
    smooth_cone(f"sideport_{spi}_frame", r1=0.45, r2=0.45, depth=0.20, segs=22, loc=(0, 0, 0), parent=sp, mat=MAT_BRASS_DARK)
    # glow
    smooth_cone(f"sideport_{spi}_glow", r1=0.38, r2=0.38, depth=0.06, segs=22, loc=(0, 0, 0.10), parent=sp, mat=MAT_OCEAN_VIEW)
    sp["_phase"] = spi * 0.30
    side_portholes.append(sp)


# --- DRAPEAU navire ----------------------------------------------------
flag_p = empty("flag_p", (-4, 7, -1))
smooth_cone("flag_pole", r1=0.03, r2=0.03, depth=1.5, segs=6, loc=(0, 0, 0), parent=flag_p, mat=MAT_BRASS_DARK)
flag_inner = empty("flag_inner_p", (0.04, 0.50, 0), parent=flag_p)
beveled_cube("flag_cloth", (0.04, 0.30, 0.40), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.20), parent=flag_inner, mat=MAT_FLAG)


# --- CRÂNE marin sur étagère -----------------------------------------
shelf_p = empty("shelf_p", (3.5, 5, -2))
beveled_cube("shelf", (1.5, 0.06, 0.50), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=shelf_p, mat=MAT_WOOD_DARK)
# skull
smooth_sphere("skull_head", r=0.20, segs=18, rings=14, loc=(0, 0.20, 0), parent=shelf_p, mat=MAT_BONE, scale=(1.0, 0.95, 0.85))
smooth_sphere("skull_jaw", r=0.13, segs=14, rings=10, loc=(0, 0.05, 0.10), parent=shelf_p, mat=MAT_BONE, scale=(1.0, 0.5, 1.0))
for ez in [0.07, -0.07]:
    smooth_sphere(f"skull_socket_{ez}", r=0.04, segs=10, rings=8, loc=(0.12, 0.25, ez), parent=shelf_p, mat=MAT_HULL)


# --- SEXTANT brass ------------------------------------------------
sextant_p = empty("sextant_p", (3, 1.65, 2))
# arc
smooth_cone("sextant_arc", r1=0.20, r2=0.20, depth=0.05, segs=22, loc=(0, 0, 0), parent=sextant_p, mat=MAT_BRASS)
# inner frame
smooth_cone("sextant_inner", r1=0.18, r2=0.18, depth=0.03, segs=22, loc=(0, 0, 0.03), parent=sextant_p, mat=MAT_BRASS_DARK)
# scope (small)
smooth_cone("sextant_scope", r1=0.025, r2=0.025, depth=0.15, segs=8, loc=(0.05, 0.20, 0), parent=sextant_p, mat=MAT_BRASS)


# --- 8 FIOLES (potions/produits chimiques sur étagère arrière) ------
shelf2_p = empty("shelf2_p", (-3.5, 5, -3.85))
beveled_cube("shelf2", (2.0, 0.06, 0.30), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.15), parent=shelf2_p, mat=MAT_WOOD_DARK)
potion_mats = [MAT_POTION_R, MAT_POTION_G, MAT_POTION_B]
for fk in range(8):
    fx = -0.80 + fk * 0.25
    fp = empty(f"fiole_{fk}_p", (fx, 0.30, 0.15), parent=shelf2_p)
    # body
    smooth_sphere(f"fiole_{fk}_body", r=0.08, segs=12, rings=8, loc=(0, 0.05, 0), parent=fp, mat=MAT_POTION_BOTTLE)
    smooth_sphere(f"fiole_{fk}_potion", r=0.06, segs=10, rings=8, loc=(0, 0.05, 0), parent=fp, mat=potion_mats[fk % 3])
    smooth_cone(f"fiole_{fk}_neck", r1=0.03, r2=0.025, depth=0.08, segs=8, loc=(0, 0.16, 0), parent=fp, mat=MAT_POTION_BOTTLE)
    smooth_cone(f"fiole_{fk}_cork", r1=0.035, r2=0.030, depth=0.04, segs=6, loc=(0, 0.22, 0), parent=fp, mat=MAT_WOOD_DARK)


# --- TUYAUX CUIVRE interconnectés (4 pipes background) ----------------
pipe_configs = [
    (-5.5, 6, -2, 4.5, 0),     # horizontal high left
    (5.5, 6, -2, 4.5, 0),      # horizontal high right
    (-3, 7, 0, 1.5, 90),       # vertical connector
    (3, 7, 0, 1.5, 90),        # vertical connector
]
for pi, (px, py, pz, plen, prot) in enumerate(pipe_configs):
    pipe = smooth_cone(f"pipe_{pi}", r1=0.10, r2=0.10, depth=plen, segs=10, loc=(px, py, pz), mat=MAT_COPPER)
    pipe.rotation_euler = (0, 0, math.radians(prot))
    smooth_sphere(f"pipe_{pi}_joint", r=0.13, segs=14, rings=10, loc=(px, py, pz), mat=MAT_BRASS_DARK)


# --- MASQUE OXYGÈNE pendant ----------------------------------------
mask_p = empty("mask_p", (4.5, 6.5, 1))
smooth_cone("mask_chain", r1=0.02, r2=0.02, depth=1.0, segs=4, loc=(0, 0.6, 0), parent=mask_p, mat=MAT_BRASS_DARK)
# main mask body
smooth_sphere("mask_body", r=0.25, segs=18, rings=14, loc=(0, 0, 0), parent=mask_p, mat=MAT_BRASS_BRIGHT, scale=(1.0, 1.2, 0.85))
# 2 eye lenses
for ek, ex in [("L", 0.10), ("R", -0.10)]:
    smooth_sphere(f"mask_lens_{ek}", r=0.06, segs=12, rings=8, loc=(ex, 0.05, 0.20), parent=mask_p, mat=MAT_GLASS)
# breathing tube
smooth_cone("mask_tube", r1=0.06, r2=0.05, depth=0.30, segs=8, loc=(0, -0.30, 0), parent=mask_p, mat=MAT_IRON)


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

    # 30 fish swim
    for fd in fish_visible:
        ang = fd["a0"] + tt * 2 * math.pi * 0.4
        bx = math.cos(ang) * fd["r"]
        by = 4.5 + math.sin(ang) * fd["r"] * 0.85
        kf(fd["p"], f, "location", (bx, by, -3.78))
        kf(fd["p"], f, "rotation_euler", (0, 0, ang + math.pi / 2))

    # 32 gauges needles : oscillate
    for gd in gauges:
        ph = gd["phase"]
        needle_ang = math.radians(40 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi))
        kf(gd["needle"], f, "rotation_euler", (0, 0, needle_ang))

    # wheel rotation slow
    kf(wheel_p, f, "rotation_euler", (math.radians(90), 0, math.radians(20 * math.sin(2 * math.pi * tt * 0.3))))

    # lever oscillates slight
    kf(lever_p, f, "rotation_euler", (0, 0, math.radians(15 + 5 * math.sin(2 * math.pi * tt * 1.2))))

    # clock hands
    hour_ang = tt * 2 * math.pi * 1.0
    minute_ang = tt * 2 * math.pi * 12.0
    second_ang = tt * 2 * math.pi * 60.0
    kf(hour_p, f, "rotation_euler", (0, 0, -hour_ang))
    kf(minute_p, f, "rotation_euler", (0, 0, -minute_ang))
    kf(second_p, f, "rotation_euler", (0, 0, -second_ang))

    # compass needle slowly rotating (subtle drift)
    compass_needle_obj = bpy.data.objects.get("compass_needle_p")
    if compass_needle_obj:
        kf(compass_needle_obj, f, "rotation_euler", (0, 0, math.radians(15 * math.sin(2 * math.pi * tt * 0.5))))

    # 6 edison lamps pulse
    for ld in edison_lamps:
        ph = ld["_phase"]
        ps = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(ld["_fil"], f, "scale", (ps, ps, ps))
        # slight sway
        kf(ld, f, "rotation_euler", (math.radians(3 * math.sin(2 * math.pi * tt * 0.8 + ph)), 0, math.radians(2 * math.cos(2 * math.pi * tt * 0.9 + ph))))

    # journal right page : turning periodically
    page_turn = math.radians(60) * (1 - math.cos(2 * math.pi * tt * 0.5)) / 2
    if right_page:
        kf(right_page, f, "rotation_euler", (0, 0, page_turn))

    # 4 side portholes pulse
    for sp in side_portholes:
        ph = sp["_phase"]
        ps = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(sp, f, "scale", (ps, ps, ps))

    # flag wave
    flag_inner_obj = bpy.data.objects.get("flag_inner_p")
    if flag_inner_obj:
        kf(flag_inner_obj, f, "rotation_euler", (0, math.radians(15 * math.sin(2 * math.pi * tt * 3)), math.radians(8 * math.cos(2 * math.pi * tt * 4))))

    # mask sway
    kf(mask_p, f, "rotation_euler", (math.radians(2 * math.sin(2 * math.pi * tt * 1.0)), 0, math.radians(3 * math.cos(2 * math.pi * tt * 0.8))))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_steampunk_submarine_interior] wrote {OUT}")
