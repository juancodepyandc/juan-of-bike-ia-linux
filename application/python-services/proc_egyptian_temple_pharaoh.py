"""
proc_egyptian_temple_pharaoh.py — 187e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Temple égyptien avec pharaon trônant :
- pyramide géante arrière-plan
- temple massif avec 8 colonnes hiéroglyphes
- statue pharaon trônant énorme
- 4 sphinx gardiens
- 12 colonnes lotus
- autel central + offrandes
- 2 sarcophages dorés
- 4 obélisques
- 6 palmiers
- 3 chameaux
- 6 prêtres processionnaires
- 50 hiéroglyphes muraux émissifs
- bassin sacré + ripples
- soleil émissif + ciel désert
- 30 grains sable

Animations multi-axes simultanées :
- pharaon statue subtle bob
- 4 sphinx head rotate
- obélisques pulse subtle
- 6 prêtres procession walk
- 6 palmiers sway
- bassin 6 ripples
- 30 grains sable drift
- soleil pulse

Sortie : output/3d/pbr_egypt_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_egypt_proc.glb"))

random.seed(0xE69D71)


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
MAT_SKY = make_mat("sky_desert", (1.0, 0.65, 0.30), roughness=1.0, emi=(0.65, 0.40, 0.20), emi_strength=1.2)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=14.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.85, 0.40), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.40), emi_strength=3.5)
MAT_SAND = make_mat("sand", (0.85, 0.70, 0.40), roughness=0.85, emi=(0.40, 0.30, 0.15), emi_strength=0.3)
MAT_STONE = make_mat("stone_sand", (0.80, 0.65, 0.40), roughness=0.7, emi=(0.30, 0.25, 0.15), emi_strength=0.3)
MAT_STONE_DARK = make_mat("stone_dark", (0.55, 0.40, 0.25), roughness=0.85)
MAT_GOLD = make_mat("gold", (0.95, 0.75, 0.30), metallic=0.95, roughness=0.20, emi=(0.45, 0.35, 0.15), emi_strength=0.8)
MAT_GOLD_BRIGHT = make_mat("gold_bright", (1.0, 0.85, 0.40), metallic=0.95, roughness=0.15, emi=(0.55, 0.45, 0.20), emi_strength=1.2)
MAT_BRONZE = make_mat("bronze", (0.65, 0.40, 0.20), metallic=0.7, roughness=0.40, emi=(0.20, 0.12, 0.06), emi_strength=0.4)
MAT_LAPIS = make_mat("lapis", (0.20, 0.30, 0.85), roughness=0.30, emi=(0.10, 0.15, 0.45), emi_strength=0.7)
MAT_TURQUOISE = make_mat("turquoise", (0.30, 0.85, 0.75), roughness=0.30, emi=(0.15, 0.45, 0.40), emi_strength=0.7)
MAT_RUBY_E = make_mat("ruby", (0.95, 0.20, 0.30), roughness=0.05, emi=(0.55, 0.10, 0.15), emi_strength=1.0)
MAT_HIEROGLYPH = make_mat("hieroglyph", (0.95, 0.80, 0.40), roughness=0.4, emi=(0.45, 0.35, 0.15), emi_strength=5.0)
MAT_WATER = make_mat("water", (0.30, 0.70, 0.85), roughness=0.10, alpha=0.65, emi=(0.20, 0.50, 0.65), emi_strength=2.0)
MAT_PALM_TRUNK = make_mat("palm_trunk", (0.35, 0.22, 0.10), roughness=0.85)
MAT_PALM_LEAF = make_mat("palm_leaf", (0.30, 0.60, 0.25), roughness=0.6, emi=(0.10, 0.25, 0.08), emi_strength=0.3)
MAT_CAMEL = make_mat("camel", (0.85, 0.65, 0.40), roughness=0.65)
MAT_PRIEST_ROBE = make_mat("priest_robe", (0.85, 0.85, 0.80), roughness=0.6, emi=(0.30, 0.30, 0.28), emi_strength=0.4)
MAT_PRIEST_SKIN = make_mat("priest_skin", (0.65, 0.45, 0.30), roughness=0.6)
MAT_HEADDRESS = make_mat("headdress", (0.85, 0.75, 0.30), metallic=0.5, roughness=0.30, emi=(0.30, 0.25, 0.10), emi_strength=0.5)
MAT_PHARAOH_SKIN = make_mat("pharaoh_skin", (0.75, 0.55, 0.35), roughness=0.6, emi=(0.30, 0.20, 0.10), emi_strength=0.4)
MAT_PHARAOH_ROBE = make_mat("pharaoh_robe", (0.95, 0.85, 0.30), metallic=0.5, roughness=0.30, emi=(0.45, 0.40, 0.10), emi_strength=0.6)
MAT_NEMES = make_mat("nemes", (0.30, 0.55, 0.95), metallic=0.4, roughness=0.40, emi=(0.10, 0.25, 0.45), emi_strength=0.5)
MAT_SARCOPHAGUS = make_mat("sarcophagus", (1.0, 0.85, 0.30), metallic=0.85, roughness=0.20, emi=(0.55, 0.45, 0.15), emi_strength=1.0)


# --- backdrop : desert sky --------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)
sun_p = empty("sun_p", (-10, 14, 11))
sun = smooth_sphere("sun", r=1.6, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.5, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=3.5, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# desert sand
ground = beveled_cube("ground", (40, 0.3, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.15, 0), mat=MAT_SAND)


# --- 3 PYRAMIDES arrière-plan ---------------------------------------
PYR_POS = [(-10, 0, 10), (10, 0, 10), (0, 0, 14)]
for pi, (px, py, pz) in enumerate(PYR_POS):
    ph_size = 4.5 if pi == 2 else 3.5
    smooth_cone(f"pyramid_{pi}", r1=ph_size, r2=0.0, depth=ph_size * 1.5, segs=4, loc=(px, ph_size * 0.75, pz), mat=MAT_STONE)
    # top cap gold (pyramidion)
    smooth_cone(f"pyramid_{pi}_cap", r1=0.20, r2=0.0, depth=0.30, segs=4, loc=(px, ph_size * 1.5 + 0.15, pz), mat=MAT_GOLD)


# --- TEMPLE MASSIF central -----------------------------------------
temple_p = empty("temple", (0, 0, 0))
# main hall
beveled_cube("temple_base", (10, 0.5, 6), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.25, 0), parent=temple_p, mat=MAT_STONE)
# steps
for sk in range(3):
    beveled_cube(f"temple_step_{sk}", (10 - sk * 0.4, 0.30, 6 - sk * 0.4), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.50 + sk * 0.30, 0), parent=temple_p, mat=MAT_STONE)


# --- 8 COLONNES HIÉROGLYPHES ----------------------------------------
hieroglyph_walls = []
COL_POS_HIERO = [(-4.5, 0, 2.5), (-1.5, 0, 2.5), (1.5, 0, 2.5), (4.5, 0, 2.5), (-4.5, 0, -2.5), (-1.5, 0, -2.5), (1.5, 0, -2.5), (4.5, 0, -2.5)]
for ci, (cx, cy, cz) in enumerate(COL_POS_HIERO):
    cp = empty(f"col_hi_{ci}_p", (cx, cy, cz))
    # base
    smooth_cone(f"col_hi_{ci}_base", r1=0.60, r2=0.55, depth=0.30, segs=10, loc=(0, 0.15, 0), parent=cp, mat=MAT_STONE_DARK)
    # main shaft
    smooth_cone(f"col_hi_{ci}_shaft", r1=0.50, r2=0.42, depth=4.0, segs=10, loc=(0, 2.3, 0), parent=cp, mat=MAT_STONE)
    # capital lotus-shaped
    smooth_cone(f"col_hi_{ci}_capital", r1=0.45, r2=0.65, depth=0.50, segs=12, loc=(0, 4.50, 0), parent=cp, mat=MAT_STONE_DARK)
    # 8 hieroglyphs émissifs sur shaft
    for hk in range(8):
        ha = hk * (math.pi * 2 / 8)
        hy = 1.0 + (hk % 4) * 0.80
        hx = math.cos(ha) * 0.51
        hz = math.sin(ha) * 0.51
        smooth_sphere(f"col_hi_{ci}_hi_{hk}", r=0.10, segs=10, rings=6, loc=(hx, hy, hz), parent=cp, mat=MAT_HIEROGLYPH, scale=(0.5, 1.5, 0.20))
        hieroglyph_walls.append(bpy.data.objects.get(f"col_hi_{ci}_hi_{hk}"))


# --- STATUE PHARAON trônante centrale -------------------------------
pharaoh_p = empty("pharaoh", (0, 0, -1))
# throne
beveled_cube("throne_base", (2.0, 1.5, 1.5), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.75, 0), parent=pharaoh_p, mat=MAT_GOLD)
# throne back
beveled_cube("throne_back", (2.0, 3.0, 0.20), bevel_offset=0.04, bevel_segments=2, loc=(0, 2.25, -0.65), parent=pharaoh_p, mat=MAT_GOLD)
# throne armrests
for ak, ax in [(0, -0.95), (1, 0.95)]:
    beveled_cube(f"throne_arm_{ak}", (0.20, 0.30, 1.5), bevel_offset=0.03, bevel_segments=2, loc=(ax, 1.65, 0), parent=pharaoh_p, mat=MAT_GOLD_BRIGHT)
# pharaoh body
# robe lower
smooth_cone("pharaoh_robe", r1=0.65, r2=0.50, depth=1.4, segs=14, loc=(0, 2.20, 0), parent=pharaoh_p, mat=MAT_PHARAOH_ROBE)
# torso
smooth_sphere("pharaoh_torso", r=0.45, segs=20, rings=14, loc=(0, 3.20, 0), parent=pharaoh_p, mat=MAT_PHARAOH_SKIN, scale=(1.0, 1.2, 0.85))
# head
head_p = empty("pharaoh_head_p", (0, 3.85, 0), parent=pharaoh_p)
smooth_sphere("pharaoh_head", r=0.30, segs=22, rings=16, loc=(0, 0, 0), parent=head_p, mat=MAT_PHARAOH_SKIN)
# nemes headdress (signature pharaoh)
smooth_sphere("pharaoh_nemes", r=0.40, segs=20, rings=14, loc=(0, 0.05, -0.05), parent=head_p, mat=MAT_NEMES, scale=(1.0, 1.3, 1.0))
# nemes side flaps
for fk, fz in [(0, 0.30), (1, -0.30)]:
    smooth_sphere(f"pharaoh_nemes_flap_{fk}", r=0.20, segs=14, rings=10, loc=(0, -0.20, fz), parent=head_p, mat=MAT_NEMES, scale=(0.5, 1.5, 0.3))
# cobra uraeus on forehead (signature)
smooth_cone("pharaoh_uraeus", r1=0.06, r2=0.0, depth=0.20, segs=6, loc=(0, 0.20, 0.32), parent=head_p, mat=MAT_GOLD_BRIGHT)
# 2 eyes
for ek, ez in [("L", 0.10), ("R", -0.10)]:
    smooth_sphere(f"pharaoh_eye_{ek}", r=0.04, segs=10, rings=8, loc=(0.25, 0.05, ez), parent=head_p, mat=MAT_LAPIS)
# beard (false beard signature)
smooth_cone("pharaoh_beard", r1=0.08, r2=0.06, depth=0.25, segs=8, loc=(0, -0.25, 0.25), parent=head_p, mat=MAT_GOLD_BRIGHT)
# crook + flail (royal symbols held by pharaoh)
# crook (hooked staff)
crook_p = empty("crook_p", (0.40, 3.20, 0.30), parent=pharaoh_p)
smooth_cone("crook_shaft", r1=0.03, r2=0.03, depth=1.0, segs=6, loc=(0, 0.20, 0), parent=crook_p, mat=MAT_GOLD)
smooth_cone("crook_hook", r1=0.05, r2=0.05, depth=0.20, segs=6, loc=(0.10, 0.75, 0), parent=crook_p, mat=MAT_GOLD)
# flail
flail_p = empty("flail_p", (-0.40, 3.20, 0.30), parent=pharaoh_p)
smooth_cone("flail_shaft", r1=0.03, r2=0.03, depth=1.0, segs=6, loc=(0, 0.20, 0), parent=flail_p, mat=MAT_GOLD)
# 3 beaded strands
for bk in range(3):
    smooth_sphere(f"flail_strand_{bk}", r=0.04, segs=8, rings=6, loc=(-0.05 + bk * 0.05, 0.75, 0), parent=flail_p, mat=MAT_LAPIS)


# --- 4 SPHINX gardiens ----------------------------------------------
sphinx_list = []
SPHINX_POS = [(-7, 0, 4), (7, 0, 4), (-7, 0, -4), (7, 0, -4)]
for si, (sx, sy, sz) in enumerate(SPHINX_POS):
    sphinx_p = empty(f"sphinx_{si}_p", (sx, sy, sz))
    sphinx_list.append(sphinx_p)
    # body (lion lying)
    smooth_sphere(f"sphinx_{si}_body", r=0.55, segs=18, rings=14, loc=(0, 0.45, 0), parent=sphinx_p, mat=MAT_STONE, scale=(1.8, 0.85, 0.95))
    # head (human face)
    head_p_s = empty(f"sphinx_{si}_head_p", (0.90, 0.85, 0), parent=sphinx_p)
    smooth_sphere(f"sphinx_{si}_head", r=0.30, segs=18, rings=14, loc=(0, 0, 0), parent=head_p_s, mat=MAT_STONE)
    # nemes headdress
    smooth_sphere(f"sphinx_{si}_nemes", r=0.38, segs=18, rings=14, loc=(0, 0.05, 0), parent=head_p_s, mat=MAT_NEMES, scale=(1.0, 1.4, 1.0))
    # 4 legs
    for lk, (lx, lz) in enumerate([(-0.5, 0.40), (-0.5, -0.40), (0.5, 0.40), (0.5, -0.40)]):
        smooth_cone(f"sphinx_{si}_leg_{lk}", r1=0.12, r2=0.10, depth=0.40, segs=8, loc=(lx, 0.20, lz), parent=sphinx_p, mat=MAT_STONE)
    sphinx_p.rotation_euler = (0, math.radians(180 if sx > 0 else 0), 0)
    sphinx_list[si] = {"p": sphinx_p, "head": head_p_s, "phase": si * 0.40}


# --- 12 COLONNES LOTUS (border path) --------------------------------
LOTUS_COL_POSITIONS = [(-5, 0, 5), (-3, 0, 5), (-1, 0, 5), (1, 0, 5), (3, 0, 5), (5, 0, 5),
                       (-5, 0, -5), (-3, 0, -5), (-1, 0, -5), (1, 0, -5), (3, 0, -5), (5, 0, -5)]
for ci, (cx, cy, cz) in enumerate(LOTUS_COL_POSITIONS):
    cp = empty(f"col_lotus_{ci}_p", (cx, cy, cz))
    # base
    smooth_cone(f"col_lotus_{ci}_base", r1=0.30, r2=0.25, depth=0.10, segs=10, loc=(0, 0.05, 0), parent=cp, mat=MAT_STONE_DARK)
    # shaft tapered
    smooth_cone(f"col_lotus_{ci}_shaft", r1=0.22, r2=0.18, depth=2.5, segs=12, loc=(0, 1.30, 0), parent=cp, mat=MAT_STONE)
    # lotus capital (5 petals)
    for pk in range(5):
        pa = pk * (math.pi * 2 / 5)
        smooth_cone(f"col_lotus_{ci}_p_{pk}", r1=0.10, r2=0.0, depth=0.30, segs=6, loc=(math.cos(pa) * 0.10, 2.65, math.sin(pa) * 0.10), parent=cp, mat=MAT_STONE)


# --- AUTEL central + offrandes -----------------------------------
altar_p = empty("altar", (0, 0, 1.5))
beveled_cube("altar_base", (1.5, 1.0, 1.0), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.50, 0), parent=altar_p, mat=MAT_GOLD)
beveled_cube("altar_top", (1.8, 0.15, 1.2), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.05, 0), parent=altar_p, mat=MAT_GOLD_BRIGHT)
# 3 offrandes (fruits/vases on top)
for ok in range(3):
    ox = -0.4 + ok * 0.4
    smooth_sphere(f"offering_{ok}", r=0.12, segs=14, rings=10, loc=(ox, 1.18, 0), parent=altar_p, mat=[MAT_RUBY_E, MAT_TURQUOISE, MAT_LAPIS][ok], scale=(1.0, 0.8, 1.0))


# --- 2 SARCOPHAGES dorés ---------------------------------------
SARC_POS = [(-3, 0, 0), (3, 0, 0)]
for ski, (sx, sy, sz) in enumerate(SARC_POS):
    sp = empty(f"sarc_{ski}_p", (sx, sy, sz))
    # body sarcophagus shape
    beveled_cube(f"sarc_{ski}_body", (0.85, 0.55, 2.0), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.40, 0), parent=sp, mat=MAT_SARCOPHAGUS)
    # lid with face
    smooth_sphere(f"sarc_{ski}_face", r=0.30, segs=18, rings=14, loc=(0, 0.85, 0.70), parent=sp, mat=MAT_SARCOPHAGUS, scale=(1.0, 1.2, 1.0))
    # nemes on lid
    smooth_sphere(f"sarc_{ski}_nemes_lid", r=0.35, segs=14, rings=10, loc=(0, 0.85, 0.65), parent=sp, mat=MAT_NEMES, scale=(1.0, 1.4, 1.0))
    # crossed arms (carved)
    beveled_cube(f"sarc_{ski}_arms", (0.70, 0.10, 0.40), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.75, 0.30), parent=sp, mat=MAT_GOLD_BRIGHT)


# --- 4 OBÉLISQUES -------------------------------------------------
obelisks = []
OBELISK_POS = [(-6, 0, -7), (-3, 0, -7), (3, 0, -7), (6, 0, -7)]
for oi, (ox, oy, oz) in enumerate(OBELISK_POS):
    op = empty(f"obelisk_{oi}_p", (ox, oy, oz))
    obelisks.append({"p": op, "phase": oi * 0.30})
    # base
    beveled_cube(f"obelisk_{oi}_base", (0.50, 0.30, 0.50), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.15, 0), parent=op, mat=MAT_STONE_DARK)
    # shaft tapered tall
    smooth_cone(f"obelisk_{oi}_shaft", r1=0.20, r2=0.10, depth=4.0, segs=4, loc=(0, 2.30, 0), parent=op, mat=MAT_STONE)
    # pyramidion top gold
    smooth_cone(f"obelisk_{oi}_top", r1=0.10, r2=0.0, depth=0.30, segs=4, loc=(0, 4.45, 0), parent=op, mat=MAT_GOLD)


# --- 6 PALMIERS ---------------------------------------------
palms = []
PALM_POS = [(-12, 0, 6), (12, 0, 6), (-14, 0, -2), (14, 0, -2), (-10, 0, -8), (10, 0, -8)]
for pi, (px, py, pz) in enumerate(PALM_POS):
    pp = empty(f"palm_{pi}_p", (px, py, pz))
    palms.append(pp)
    # trunk 5 segs slightly curved
    cur_y = 0
    for sg in range(5):
        seg_y = cur_y + 0.85
        smooth_cone(f"palm_{pi}_t_{sg}", r1=0.15 - sg * 0.015, r2=0.13 - sg * 0.015, depth=0.90, segs=10, loc=(math.cos(sg * 0.5) * 0.05, seg_y, math.sin(sg * 0.5) * 0.05), parent=pp, mat=MAT_PALM_TRUNK)
        cur_y += 0.90
    # 7 fronds (palm leaves)
    for lk in range(7):
        la = lk * (math.pi * 2 / 7)
        leaf_p = empty(f"palm_{pi}_lp_{lk}", (math.cos(la) * 0.2, cur_y, math.sin(la) * 0.2), parent=pp)
        leaf_p.rotation_euler = (math.radians(-15 - random.uniform(0, 15)), -la, 0)
        smooth_sphere(f"palm_{pi}_l_{lk}", r=0.50, segs=14, rings=10, loc=(0, -0.30, 1.0), parent=leaf_p, mat=MAT_PALM_LEAF, scale=(0.30, 0.05, 2.5))
    pp["_phase"] = pi * 0.30


# --- 3 CHAMEAUX ------------------------------------------------
camels = []
CAMEL_POS = [(-9, 0, -3), (-9.5, 0, -1.5), (-10, 0, 0)]
for ci, (cx, cy, cz) in enumerate(CAMEL_POS):
    cp = empty(f"camel_{ci}_p", (cx, cy, cz))
    camels.append({"p": cp, "phase": ci * 0.40})
    smooth_sphere(f"camel_{ci}_body", r=0.55, segs=18, rings=14, loc=(0, 1.0, 0), parent=cp, mat=MAT_CAMEL, scale=(1.6, 0.85, 1.0))
    smooth_sphere(f"camel_{ci}_hump1", r=0.30, segs=14, rings=10, loc=(-0.20, 1.50, 0), parent=cp, mat=MAT_CAMEL)
    smooth_sphere(f"camel_{ci}_hump2", r=0.30, segs=14, rings=10, loc=(0.20, 1.45, 0), parent=cp, mat=MAT_CAMEL)
    neck = smooth_cone(f"camel_{ci}_neck", r1=0.18, r2=0.15, depth=0.85, segs=10, loc=(0.80, 1.45, 0), parent=cp, mat=MAT_CAMEL)
    neck.rotation_euler = (0, 0, math.radians(-55))
    smooth_sphere(f"camel_{ci}_head", r=0.18, segs=14, rings=10, loc=(1.20, 1.85, 0), parent=cp, mat=MAT_CAMEL)
    # 4 legs
    for lk, (lx, lz) in enumerate([(-0.30, -0.30), (0.30, -0.30), (-0.30, 0.30), (0.30, 0.30)]):
        smooth_cone(f"camel_{ci}_leg_{lk}", r1=0.08, r2=0.07, depth=1.0, segs=8, loc=(lx, 0.50, lz), parent=cp, mat=MAT_CAMEL)


# --- 6 PRÊTRES processionnaires ------------------------------
priests = []
PRIEST_POS = [(-2, 0, 4), (-1, 0, 4), (0, 0, 4), (1, 0, 4), (2, 0, 4), (0, 0, 5)]
for pi, (px, py, pz) in enumerate(PRIEST_POS):
    pp = empty(f"priest_{pi}_p", (px, py, pz))
    priests.append({"p": pp, "phase": pi * 0.30, "base": (px, py, pz)})
    # robe
    smooth_cone(f"priest_{pi}_robe", r1=0.20, r2=0.30, depth=0.95, segs=12, loc=(0, 0.50, 0), parent=pp, mat=MAT_PRIEST_ROBE)
    # head
    smooth_sphere(f"priest_{pi}_head", r=0.14, segs=14, rings=10, loc=(0, 1.10, 0), parent=pp, mat=MAT_PRIEST_SKIN)
    # headdress
    smooth_sphere(f"priest_{pi}_headdress", r=0.16, segs=14, rings=10, loc=(0, 1.15, 0), parent=pp, mat=MAT_HEADDRESS, scale=(1.0, 1.3, 1.0))


# --- 50 HIÉROGLYPHES muraux émissifs (back wall) ---------------
for hi in range(50):
    hx = -7 + (hi % 10) * 1.4
    hy = 1 + (hi // 10) * 1.3
    smooth_sphere(f"wall_hi_{hi}", r=0.10, segs=10, rings=6, loc=(hx, hy, -5.9), mat=MAT_HIEROGLYPH, scale=(0.5, 1.5, 0.2))


# --- BASSIN SACRÉ --------------------------------------------
pool_p = empty("pool", (5, 0, -3))
# rim stone
smooth_cone("pool_rim", r1=1.5, r2=1.3, depth=0.30, segs=22, loc=(0, 0.15, 0), parent=pool_p, mat=MAT_STONE_DARK)
# water
smooth_cone("pool_water", r1=1.2, r2=1.2, depth=0.10, segs=22, loc=(0, 0.30, 0), parent=pool_p, mat=MAT_WATER)
# 6 ripples
ripples = []
for rk in range(6):
    rr = 0.4 + (rk % 3) * 0.3
    rip = smooth_cone(f"ripple_{rk}", r1=rr, r2=rr * 1.05, depth=0.03, segs=18, loc=(0, 0.32, 0), parent=pool_p, mat=MAT_WATER)
    rip["_phase"] = rk * 0.25
    ripples.append(rip)


# --- 30 GRAINS sable drift ----------------------------------
sand_grains = []
for gk in range(30):
    gx = random.uniform(-13, 13)
    gy = random.uniform(0.3, 3)
    gz = random.uniform(-10, 10)
    grain = smooth_sphere(f"grain_{gk}", r=random.uniform(0.04, 0.08), segs=8, rings=6, loc=(gx, gy, gz), mat=MAT_SAND)
    grain["_base"] = (gx, gy, gz)
    grain["_phase"] = gk * 0.15
    sand_grains.append(grain)


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

    # pharaoh subtle bob
    kf(pharaoh_p, f, "rotation_euler", (math.radians(2 * math.sin(2 * math.pi * tt * 0.5)), 0, 0))

    # 4 sphinx : head rotate
    for sx_d in sphinx_list:
        ph = sx_d["phase"]
        kf(sx_d["head"], f, "rotation_euler", (0, math.radians(15 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)), 0))

    # 4 obelisks pulse subtle
    for ob in obelisks:
        ph = ob["phase"]
        ps = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        kf(ob["p"], f, "scale", (ps, ps, ps))

    # 6 priests procession walk
    for pi_d in priests:
        bx_, by_, bz_ = pi_d["base"]
        ph = pi_d["phase"]
        nx = bx_ + 0.3 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        nz = bz_ + 0.3 * math.cos(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(pi_d["p"], f, "location", (nx, by_, nz))

    # 6 palms sway
    for pi_p in palms:
        ph = pi_p["_phase"]
        sw = math.radians(3 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi))
        kf(pi_p, f, "rotation_euler", (sw, 0, math.radians(2 * math.cos(2 * math.pi * tt * 0.8 + ph * math.pi))))

    # 6 ripples expansion
    for ri_d in ripples:
        ph = ri_d["_phase"]
        local = (tt * 2 + ph) % 1.0
        sc = 1.0 + local * 1.5
        kf(ri_d, f, "scale", (sc, 1.0, sc))

    # 30 sand grains drift
    for gr in sand_grains:
        bx_, by_, bz_ = gr["_base"]
        ph = gr["_phase"]
        nx = bx_ + 0.30 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        nz = bz_ + 0.25 * math.cos(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(gr, f, "location", (nx, by_, nz))

    # sun pulse + halos breathe
    sp = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 1.5)
    kf(sun, f, "scale", (sp, sp, sp))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_egyptian_temple_pharaoh] wrote {OUT}")
