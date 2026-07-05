"""
proc_witch_cottage_forest.py — 164e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Chaumière de sorcière dans forêt enchantée nocturne :
- cottage tordu bevelé : walls + roof asymétrique incliné + cheminée fumante
- porte arquée + 4 fenêtres émissives jaunes
- chat noir sur porche
- balai magique posé contre mur
- chaudron bouillant émissif jardin
- 5 arbres tortueux forêt sombre
- 8 corbeaux perchés
- 6 lanternes citrouille émissives
- sentier pierres mossy
- lune émissive énorme + halos
- 40 étoiles + 30 lucioles spirales
- ground brouillard alpha
- grimoire ouvert flottant émissif
- sorcière sur balai dans ciel
- 5 bouquets herbes pendues

Animations multi-axes simultanées :
- sorcière vole en cercle large sur balai + bank + cape ondule
- chaudron bouillon : 8 bulles + 3 steam puffs
- 4 fenêtres pulse émission
- 6 lanternes citrouille pulse + sway
- 8 corbeaux flap occasionnel + dart
- 30 lucioles spirales montantes
- brouillard ground drift
- grimoire flotte Y + pages tournent
- 5 arbres sway léger
- lune halo breathe

Sortie : output/3d/pbr_witchcottage_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_witchcottage_proc.glb"))

random.seed(0xC07AEE)


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
MAT_SKY = make_mat("sky_night", (0.05, 0.08, 0.18), roughness=1.0, emi=(0.05, 0.08, 0.18), emi_strength=0.6)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.0)
MAT_MOON = make_mat("moon", (0.95, 0.92, 0.85), roughness=0.0, emi=(0.95, 0.92, 0.85), emi_strength=10.0)
MAT_MOON_HALO = make_mat("moon_halo", (0.95, 0.92, 0.85), roughness=0.0, alpha=0.30, emi=(0.95, 0.92, 0.85), emi_strength=2.5)
MAT_GROUND = make_mat("ground", (0.10, 0.08, 0.06), roughness=0.95)
MAT_GRASS = make_mat("grass_dark", (0.15, 0.20, 0.10), roughness=0.85, emi=(0.05, 0.10, 0.05), emi_strength=0.2)
MAT_FOG = make_mat("fog", (0.30, 0.35, 0.40), roughness=1.0, alpha=0.30, emi=(0.20, 0.25, 0.30), emi_strength=0.5)
MAT_STONE = make_mat("stone", (0.35, 0.33, 0.30), roughness=0.85)
MAT_MOSS = make_mat("moss", (0.20, 0.40, 0.18), roughness=0.7, emi=(0.05, 0.20, 0.08), emi_strength=0.4)
MAT_COTTAGE_WALL = make_mat("cottage_wall", (0.55, 0.35, 0.20), roughness=0.7)
MAT_COTTAGE_ROOF = make_mat("cottage_roof", (0.25, 0.15, 0.10), roughness=0.75)
MAT_COTTAGE_WINDOW = make_mat("cottage_window", (1.0, 0.80, 0.30), roughness=0.0, emi=(1.0, 0.80, 0.30), emi_strength=12.0)
MAT_COTTAGE_DOOR = make_mat("cottage_door", (0.30, 0.18, 0.10), roughness=0.7)
MAT_TRUNK = make_mat("trunk_dark", (0.15, 0.10, 0.06), roughness=0.95)
MAT_LEAVES = make_mat("leaves_dark", (0.10, 0.20, 0.10), roughness=0.7, emi=(0.04, 0.10, 0.05), emi_strength=0.2)
MAT_CHIMNEY = make_mat("chimney", (0.30, 0.25, 0.20), roughness=0.85)
MAT_SMOKE = make_mat("smoke", (0.55, 0.50, 0.55), roughness=1.0, alpha=0.40, emi=(0.30, 0.28, 0.32), emi_strength=1.0)
MAT_BROOM_STICK = make_mat("broom_stick", (0.30, 0.18, 0.08), roughness=0.85)
MAT_BROOM_BRISTLE = make_mat("broom_bristle", (0.45, 0.30, 0.15), roughness=0.85)
MAT_CAT = make_mat("cat_black", (0.06, 0.05, 0.05), roughness=0.5)
MAT_CAT_EYE = make_mat("cat_eye", (0.30, 0.95, 0.30), roughness=0.0, emi=(0.30, 0.95, 0.30), emi_strength=12.0)
MAT_RAVEN = make_mat("raven", (0.08, 0.08, 0.10), roughness=0.5)
MAT_RAVEN_EYE = make_mat("raven_eye", (0.95, 0.30, 0.30), roughness=0.0, emi=(0.95, 0.30, 0.30), emi_strength=8.0)
MAT_CAULDRON = make_mat("cauldron", (0.20, 0.18, 0.18), metallic=0.7, roughness=0.50)
MAT_CAULDRON_LIQ = make_mat("cauldron_liq", (0.55, 0.95, 0.40), roughness=0.10, alpha=0.85, emi=(0.55, 0.95, 0.40), emi_strength=7.0)
MAT_FLAME = make_mat("flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=14.0)
MAT_PUMPKIN = make_mat("pumpkin", (0.95, 0.55, 0.15), roughness=0.5, emi=(0.45, 0.20, 0.05), emi_strength=0.8)
MAT_PUMPKIN_GLOW = make_mat("pumpkin_glow", (1.0, 0.65, 0.20), roughness=0.0, emi=(1.0, 0.65, 0.20), emi_strength=11.0)
MAT_WITCH_HAT = make_mat("witch_hat", (0.06, 0.05, 0.10), roughness=0.6)
MAT_WITCH_DRESS = make_mat("witch_dress", (0.12, 0.08, 0.20), roughness=0.7, emi=(0.05, 0.03, 0.08), emi_strength=0.3)
MAT_WITCH_SKIN = make_mat("witch_skin", (0.55, 0.65, 0.50), roughness=0.6, emi=(0.20, 0.25, 0.18), emi_strength=0.3)
MAT_FIREFLY = make_mat("firefly", (0.85, 1.0, 0.40), roughness=0.0, emi=(0.85, 1.0, 0.40), emi_strength=10.0)
MAT_GRIMOIRE = make_mat("grimoire_cover", (0.30, 0.10, 0.20), roughness=0.6, emi=(0.15, 0.05, 0.10), emi_strength=0.5)
MAT_GRIMOIRE_PAGE = make_mat("grimoire_page", (0.85, 0.75, 0.55), roughness=0.5, emi=(0.45, 0.40, 0.30), emi_strength=2.5)
MAT_HERBS = make_mat("herbs", (0.30, 0.45, 0.15), roughness=0.7, emi=(0.10, 0.15, 0.05), emi_strength=0.3)


# --- backdrop : night sky + ground -----------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 10), mat=MAT_SKY)
ground = beveled_cube("ground", (30, 0.1, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND)
# grass patches
for gk in range(8):
    gx = random.uniform(-12, 12)
    gz = random.uniform(-3, 7)
    smooth_sphere(f"grass_{gk}", r=random.uniform(0.5, 1.2), segs=14, rings=8, loc=(gx, 0.05, gz), mat=MAT_GRASS, scale=(1.0, 0.10, 1.0))

# 40 stars
for i in range(40):
    smooth_sphere(f"star_{i}", r=random.uniform(0.07, 0.12), segs=10, rings=8, loc=(random.uniform(-18, 18), random.uniform(12, 14), random.uniform(8, 14)), mat=MAT_STAR)

# moon + halos (large)
moon_p = empty("moon_p", (-9, 12, 8))
smooth_sphere("moon", r=1.5, segs=28, rings=20, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON)
moon_halo_1 = smooth_sphere("moon_halo_1", r=2.5, segs=22, rings=14, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)
moon_halo_2 = smooth_sphere("moon_halo_2", r=3.5, segs=20, rings=12, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)

# ground fog (10 puffs)
fog_puffs = []
for fk in range(10):
    fx = random.uniform(-12, 12)
    fz = random.uniform(-3, 6)
    fp = smooth_sphere(f"fog_{fk}", r=random.uniform(1.0, 1.8), segs=14, rings=8, loc=(fx, 0.30, fz), mat=MAT_FOG, scale=(1.0, 0.15, 1.0))
    fp["_base_x"] = fx
    fp["_phase"] = fk * 0.30
    fog_puffs.append(fp)


# --- COTTAGE TORDU --------------------------------------------------------
cottage_p = empty("cottage_p", (0, 0, 1.5))
# main walls (cube slightly tilted for "twisted" feel)
walls = beveled_cube("walls", (3.5, 2.8, 3.0), bevel_offset=0.06, bevel_segments=3, loc=(0, 1.40, 0), parent=cottage_p, mat=MAT_COTTAGE_WALL)
walls.rotation_euler = (0, 0, math.radians(3))

# 4 windows (yellow émissifs)
window_positions = [(-1.8, 1.8, 0.5, "L1"), (-1.8, 1.8, -0.5, "L2"), (1.8, 1.8, 0.5, "R1"), (1.8, 1.8, -0.5, "R2")]
window_objects = []
for (wx, wy, wz, wn) in window_positions:
    win = smooth_sphere(f"window_{wn}", r=0.30, segs=14, rings=10, loc=(wx, wy, wz), parent=cottage_p, mat=MAT_COTTAGE_WINDOW, scale=(0.20, 1.0, 1.0))
    window_objects.append(win)
# front windows (toward viewer)
for (fwx, fwn) in [(-0.8, "F1"), (0.8, "F2")]:
    win = beveled_cube(f"window_F_{fwn}", (0.50, 0.50, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(fwx, 1.80, 1.55), parent=cottage_p, mat=MAT_COTTAGE_WINDOW)
    window_objects.append(win)

# arched door
door_p = empty("door_p", (0, 0.80, 1.55), parent=cottage_p)
# door base (rectangular)
beveled_cube("door_base", (0.50, 1.10, 0.10), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.10, 0), parent=door_p, mat=MAT_COTTAGE_DOOR)
# arched top
smooth_cone("door_arch", r1=0.30, r2=0.30, depth=0.10, segs=12, loc=(0, 0.85, 0), parent=door_p, mat=MAT_COTTAGE_DOOR)
# handle
smooth_sphere("door_handle", r=0.06, segs=10, rings=6, loc=(0.18, 0.20, 0.10), parent=door_p, mat=MAT_PUMPKIN_GLOW)

# roof (asymmetric inclined) — 2 cone pieces
roof_p = empty("roof_p", (0, 2.80, 0), parent=cottage_p)
# main roof cone (asymmetric)
roof_main = smooth_cone("roof_main", r1=2.50, r2=0.0, depth=2.5, segs=14, loc=(0.30, 1.25, 0), parent=roof_p, mat=MAT_COTTAGE_ROOF)
roof_main.rotation_euler = (0, 0, math.radians(-10))
# crooked overhang
roof_overhang = smooth_cone("roof_overhang", r1=2.0, r2=1.5, depth=0.20, segs=14, loc=(0, 0.10, 0), parent=roof_p, mat=MAT_COTTAGE_ROOF)

# chimney (tilted)
chim_p = empty("chim_p", (1.0, 3.5, 0), parent=cottage_p)
chim_p.rotation_euler = (0, 0, math.radians(8))
beveled_cube("chimney", (0.40, 1.6, 0.40), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.80, 0), parent=chim_p, mat=MAT_CHIMNEY)
# chimney top opening
smooth_cone("chimney_top", r1=0.20, r2=0.22, depth=0.10, segs=12, loc=(0, 1.65, 0), parent=chim_p, mat=MAT_CHIMNEY)

# chimney smoke (4 puffs rising)
chim_smokes = []
for sk in range(4):
    sp = smooth_sphere(f"chim_smoke_{sk}", r=0.30, segs=14, rings=10, loc=(0, 1.80 + sk * 0.50, 0), parent=chim_p, mat=MAT_SMOKE, scale=(1.2, 1.0, 1.2))
    sp["_phase"] = sk * 0.25
    chim_smokes.append(sp)

# porch (front)
porch_p = empty("porch_p", (0, 0, 2.2))
beveled_cube("porch_base", (3.0, 0.20, 1.0), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.10, 0), parent=porch_p, mat=MAT_COTTAGE_WALL)


# --- chat noir sur porche ------------------------------------------------
cat_p = empty("cat_p", (-1.0, 0.30, 2.4))
# body
smooth_sphere("cat_body", r=0.18, segs=18, rings=14, loc=(0, 0.20, 0), parent=cat_p, mat=MAT_CAT, scale=(1.3, 1.0, 1.0))
# head
smooth_sphere("cat_head", r=0.13, segs=16, rings=12, loc=(0.18, 0.32, 0), parent=cat_p, mat=MAT_CAT)
# 2 ears
for ek, ez in [("L", 0.06), ("R", -0.06)]:
    smooth_cone(f"cat_ear_{ek}", r1=0.04, r2=0.0, depth=0.08, segs=8, loc=(0.18, 0.45, ez), parent=cat_p, mat=MAT_CAT)
# 2 eyes glowing
for ek, ez in [("L", 0.04), ("R", -0.04)]:
    smooth_sphere(f"cat_eye_{ek}", r=0.022, segs=10, rings=6, loc=(0.26, 0.33, ez), parent=cat_p, mat=MAT_CAT_EYE)
# tail curled
tail_p = empty("cat_tail_p", (-0.15, 0.20, 0), parent=cat_p)
for tk in range(4):
    smooth_sphere(f"cat_tail_{tk}", r=0.035, segs=10, rings=6, loc=(-0.08 - tk * 0.08, 0.05 + tk * 0.05, 0), parent=tail_p, mat=MAT_CAT)


# --- balai magique posé contre mur ---------------------------------------
broom_static_p = empty("broom_static_p", (-2.0, 0.10, 2.0))
broom_static_p.rotation_euler = (0, 0, math.radians(75))
# stick
smooth_cone("broom_static_stick", r1=0.04, r2=0.04, depth=1.4, segs=8, loc=(0, 0.70, 0), parent=broom_static_p, mat=MAT_BROOM_STICK)
# bristles
for bk in range(12):
    ba = bk * (math.pi * 2 / 12)
    smooth_cone(f"broom_static_b_{bk}", r1=0.02, r2=0.0, depth=0.25, segs=4, loc=(math.cos(ba) * 0.06, 0, math.sin(ba) * 0.06), parent=broom_static_p, mat=MAT_BROOM_BRISTLE)


# --- chaudron bouillant émissif jardin ----------------------------------
cauldron_p = empty("cauldron_p", (3.0, 0, 2.5))
# body
caul_body = smooth_sphere("caul_body", r=0.55, segs=22, rings=16, loc=(0, 0.50, 0), parent=cauldron_p, mat=MAT_CAULDRON, scale=(1.0, 0.85, 1.0))
# rim
smooth_cone("caul_rim", r1=0.58, r2=0.55, depth=0.08, segs=18, loc=(0, 0.85, 0), parent=cauldron_p, mat=MAT_CAULDRON)
# 3 legs tripod
for lg in range(3):
    la = lg * (math.pi * 2 / 3)
    smooth_cone(f"caul_leg_{lg}", r1=0.06, r2=0.05, depth=0.30, segs=8, loc=(math.cos(la) * 0.45, 0.15, math.sin(la) * 0.45), parent=cauldron_p, mat=MAT_CAULDRON)
# liquid émissif vert
liquid = smooth_sphere("caul_liq", r=0.50, segs=22, rings=14, loc=(0, 0.78, 0), parent=cauldron_p, mat=MAT_CAULDRON_LIQ, scale=(1.0, 0.20, 1.0))
# 8 bubbles inside
caul_bubs = []
for cb in range(8):
    ca = cb * (math.pi * 2 / 8) + 0.3
    cr = 0.30
    bub = smooth_sphere(f"caul_bub_{cb}", r=0.08, segs=12, rings=8, loc=(math.cos(ca) * cr * 0.5, 0.80, math.sin(ca) * cr * 0.5), parent=cauldron_p, mat=MAT_CAULDRON_LIQ)
    bub["_phase"] = cb * 0.20
    caul_bubs.append(bub)
# 3 steam puffs above
caul_steams = []
for st in range(3):
    sp = smooth_sphere(f"caul_steam_{st}", r=0.30, segs=14, rings=10, loc=(0, 1.20 + st * 0.50, 0), parent=cauldron_p, mat=MAT_SMOKE, scale=(1.3, 1.0, 1.3))
    sp["_phase"] = st * 0.30
    caul_steams.append(sp)
# fire underneath
caul_fire = smooth_sphere("caul_fire", r=0.35, segs=16, rings=12, loc=(0, 0.15, 0), parent=cauldron_p, mat=MAT_FLAME, scale=(1.0, 0.80, 1.0))


# --- 5 arbres tortueux forêt sombre --------------------------------------
TREE_POSITIONS = [(-6, 0, 4), (6, 0, 4), (-8, 0, -2), (8, 0, -2), (-4, 0, 6)]
trees = []
for ti, (tx, ty, tz) in enumerate(TREE_POSITIONS):
    tp = empty(f"tree_{ti}_p", (tx, ty, tz))
    trees.append(tp)
    # trunk twisted (3 segs with rotation)
    cur = tp
    for sg in range(3):
        seg_p = empty(f"tree_{ti}_seg_p_{sg}", (0, 0.80, 0), parent=cur)
        seg_p.rotation_euler = (math.radians(random.uniform(-8, 8)), 0, math.radians(random.uniform(-10, 10)))
        smooth_cone(f"tree_{ti}_seg_{sg}", r1=0.28 - sg * 0.04, r2=0.22 - sg * 0.04, depth=1.6, segs=10, loc=(0, 0.80, 0), parent=seg_p, mat=MAT_TRUNK)
        cur = seg_p
    # twisted branches (5 per tree)
    for bk in range(5):
        ba = bk * (math.pi * 2 / 5) + random.uniform(-0.2, 0.2)
        bx_off = math.cos(ba) * 0.40
        bz_off = math.sin(ba) * 0.40
        smooth_cone(f"tree_{ti}_br_{bk}", r1=0.10, r2=0.04, depth=random.uniform(1.0, 1.8), segs=8, loc=(bx_off, 0, bz_off), parent=cur, mat=MAT_TRUNK)
    # 8 leaves clusters per tree at top
    for lk in range(8):
        la = lk * (math.pi * 2 / 8) + random.uniform(-0.2, 0.2)
        lr = random.uniform(0.4, 0.7)
        lx = math.cos(la) * lr
        lz = math.sin(la) * lr
        smooth_sphere(f"tree_{ti}_lf_{lk}", r=random.uniform(0.30, 0.50), segs=14, rings=10, loc=(lx, 1.0 + random.uniform(-0.3, 0.3), lz), parent=cur, mat=MAT_LEAVES, scale=(1.0, 0.6, 1.0))


# --- 8 corbeaux perchés sur branches/cottage ------------------------------
ravens = []
RAVEN_POSITIONS = [(-5.5, 3.5, 4), (6.5, 3.0, 4), (-7.5, 3.0, -1), (7, 3.5, -1.5),
                    (2.5, 3.0, 1.0), (-2.5, 3.0, 1.0), (4.5, 3.8, 5), (-4, 3.8, 5)]
for ri, (rx, ry, rz) in enumerate(RAVEN_POSITIONS):
    rp = empty(f"raven_{ri}_p", (rx, ry, rz))
    ravens.append({"p": rp, "phase": ri * 0.5})
    # body
    smooth_sphere(f"raven_{ri}_body", r=0.15, segs=14, rings=10, loc=(0, 0, 0), parent=rp, mat=MAT_RAVEN, scale=(1.4, 0.9, 0.9))
    # head
    smooth_sphere(f"raven_{ri}_head", r=0.09, segs=12, rings=8, loc=(0.15, 0.08, 0), parent=rp, mat=MAT_RAVEN)
    # beak
    smooth_cone(f"raven_{ri}_beak", r1=0.025, r2=0.0, depth=0.10, segs=6, loc=(0.24, 0.08, 0), parent=rp, mat=MAT_CAULDRON)
    # eye
    smooth_sphere(f"raven_{ri}_eye", r=0.022, segs=8, rings=6, loc=(0.20, 0.10, 0.06), parent=rp, mat=MAT_RAVEN_EYE)
    # 2 wings (folded)
    wL = empty(f"raven_{ri}_wL", (0, 0.05, 0.06), parent=rp)
    wR = empty(f"raven_{ri}_wR", (0, 0.05, -0.06), parent=rp)
    smooth_sphere(f"raven_{ri}_wL_b", r=0.12, segs=12, rings=8, loc=(0, 0, 0.05), parent=wL, mat=MAT_RAVEN, scale=(1.2, 0.10, 1.2))
    smooth_sphere(f"raven_{ri}_wR_b", r=0.12, segs=12, rings=8, loc=(0, 0, -0.05), parent=wR, mat=MAT_RAVEN, scale=(1.2, 0.10, 1.2))
    ravens[ri]["wL"] = wL
    ravens[ri]["wR"] = wR


# --- 6 lanternes citrouille émissives ------------------------------------
pumpkins = []
PUMP_POSITIONS = [(-2.5, 0.20, 3.5), (2.5, 0.20, 3.5), (-3.5, 0.20, 1), (3.5, 0.20, 1), (-1.5, 0.20, 4.5), (1.5, 0.20, 4.5)]
for pi, (px, py, pz) in enumerate(PUMP_POSITIONS):
    pp = empty(f"pump_{pi}_p", (px, py, pz))
    pumpkins.append(pp)
    # pumpkin body (ribbed sphere)
    body = smooth_sphere(f"pump_{pi}_body", r=0.30, segs=24, rings=16, loc=(0, 0.20, 0), parent=pp, mat=MAT_PUMPKIN, scale=(1.0, 0.85, 1.0))
    # stem
    smooth_cone(f"pump_{pi}_stem", r1=0.05, r2=0.04, depth=0.10, segs=8, loc=(0, 0.50, 0), parent=pp, mat=MAT_TRUNK)
    # glow inside (2 eyes + mouth shape)
    smooth_sphere(f"pump_{pi}_glow", r=0.20, segs=16, rings=12, loc=(0, 0.20, 0), parent=pp, mat=MAT_PUMPKIN_GLOW)
    # carved eyes (small black sockets)
    for ek, ez in [("L", 0.05), ("R", -0.05)]:
        smooth_cone(f"pump_{pi}_eye_{ek}", r1=0.05, r2=0.05, depth=0.05, segs=6, loc=(0.18, 0.30, ez), parent=pp, mat=MAT_TRUNK)
    pp["_phase"] = pi * 0.35


# --- sentier pierres mossy --------------------------------------------
for sk in range(10):
    sx = -1 + sk * 0.4
    sz = 5.5 - sk * 0.35
    smooth_sphere(f"path_{sk}", r=0.25, segs=14, rings=8, loc=(sx, 0.05, sz), mat=MAT_STONE, scale=(1.0, 0.15, 0.85))
    # tiny moss
    smooth_sphere(f"path_{sk}_moss", r=0.10, segs=10, rings=6, loc=(sx + random.uniform(-0.1, 0.1), 0.10, sz), mat=MAT_MOSS, scale=(1.0, 0.20, 1.0))


# --- 30 lucioles spirales --------------------------------------------
fireflies = []
for fk in range(30):
    a = fk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 9)
    y = random.uniform(1, 6)
    fp_obj = smooth_sphere(f"firefly_{fk}", r=random.uniform(0.05, 0.08), segs=8, rings=6, loc=(math.cos(a) * r, y, math.sin(a) * r), mat=MAT_FIREFLY)
    fp_obj["_a"] = a
    fp_obj["_r0"] = r
    fp_obj["_y0"] = y
    fp_obj["_phase"] = fk * 0.21
    fireflies.append(fp_obj)


# --- grimoire ouvert flottant émissif -------------------------------------
grimoire_p = empty("grimoire_p", (-3, 1.5, 3.5))
# left page
left_page = beveled_cube("grim_left", (0.55, 0.04, 0.45), bevel_offset=0.02, bevel_segments=2, loc=(-0.28, 0.04, 0), parent=grimoire_p, mat=MAT_GRIMOIRE_PAGE)
# right page
right_page = beveled_cube("grim_right", (0.55, 0.04, 0.45), bevel_offset=0.02, bevel_segments=2, loc=(0.28, 0.04, 0), parent=grimoire_p, mat=MAT_GRIMOIRE_PAGE)
# spine
beveled_cube("grim_spine", (0.08, 0.10, 0.45), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.08, 0), parent=grimoire_p, mat=MAT_GRIMOIRE)
# floating page that turns
turning_page = beveled_cube("grim_turn_page", (0.50, 0.02, 0.42), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.10, 0), parent=grimoire_p, mat=MAT_GRIMOIRE_PAGE)


# --- 5 bouquets herbes pendues ------------------------------------------
HERB_POSITIONS = [(-1.5, 2.5, 1.55), (-0.5, 2.5, 1.55), (0.5, 2.5, 1.55), (1.5, 2.5, 1.55), (2.5, 2.5, 1.55)]
for hi, (hx, hy, hz) in enumerate(HERB_POSITIONS):
    hp = empty(f"herb_{hi}_p", (hx, hy, hz))
    # 3 stems hanging down
    for sk in range(3):
        sa = (sk - 1) * 0.10
        stems = smooth_cone(f"herb_{hi}_st_{sk}", r1=0.03, r2=0.02, depth=0.45, segs=6, loc=(sa, -0.20, 0), parent=hp, mat=MAT_HERBS)
        # tiny leaves
        for lk in range(3):
            smooth_sphere(f"herb_{hi}_lf_{sk}_{lk}", r=0.05, segs=10, rings=6, loc=(sa + 0.04 * math.cos(lk * math.pi / 1.5), -0.10 - lk * 0.12, 0.03 * math.sin(lk * math.pi / 1.5)), parent=hp, mat=MAT_HERBS, scale=(1.0, 0.4, 0.5))


# --- SORCIÈRE SUR BALAI dans ciel ---------------------------------------
witch_p = empty("witch_p", (5, 8, -2))
# broom stick (long)
broom_p = empty("broom_p", (0, 0, 0), parent=witch_p)
smooth_cone("broom_stick", r1=0.05, r2=0.04, depth=2.0, segs=8, loc=(0, 0, 0), parent=broom_p, mat=MAT_BROOM_STICK)
broom_obj = bpy.data.objects.get("broom_stick")
if broom_obj:
    broom_obj.rotation_euler = (0, 0, math.radians(90))
# bristles back
for bk in range(15):
    ba = bk * (math.pi * 2 / 15)
    smooth_cone(f"broom_b_{bk}", r1=0.025, r2=0.0, depth=0.35, segs=4, loc=(-0.95, math.cos(ba) * 0.10, math.sin(ba) * 0.10), parent=broom_p, mat=MAT_BROOM_BRISTLE)
# witch body (sitting on broom)
witch_body_p = empty("witch_body_p", (0.10, 0.25, 0), parent=witch_p)
# dress
smooth_cone("witch_dress", r1=0.25, r2=0.15, depth=0.60, segs=14, loc=(0, 0.30, 0), parent=witch_body_p, mat=MAT_WITCH_DRESS)
# head
smooth_sphere("witch_head", r=0.15, segs=18, rings=14, loc=(0, 0.65, 0), parent=witch_body_p, mat=MAT_WITCH_SKIN, scale=(1.0, 1.1, 1.0))
# hat (witch hat — cone with brim)
hat_p = empty("hat_p", (0, 0.80, 0), parent=witch_body_p)
# brim
smooth_cone("hat_brim", r1=0.30, r2=0.30, depth=0.04, segs=14, loc=(0, 0, 0), parent=hat_p, mat=MAT_WITCH_HAT)
# cone
smooth_cone("hat_cone", r1=0.18, r2=0.0, depth=0.60, segs=14, loc=(0, 0.30, 0), parent=hat_p, mat=MAT_WITCH_HAT)
# cape behind
cape_p = empty("cape_p", (-0.10, 0.30, 0), parent=witch_body_p)
beveled_cube("cape", (0.50, 0.55, 0.06), bevel_offset=0.04, bevel_segments=2, loc=(-0.20, 0, 0), parent=cape_p, mat=MAT_WITCH_DRESS)


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

    # witch flying in large circle
    witch_ang = tt * 2 * math.pi * 0.7
    wx = 0 + math.cos(witch_ang) * 6
    wy = 7 + 1.5 * math.sin(2 * math.pi * tt * 1.0)
    wz = math.sin(witch_ang) * 5
    kf(witch_p, f, "location", (wx, wy, wz))
    # face direction + bank
    bank = math.radians(20 * math.sin(2 * math.pi * tt * 1.5))
    kf(witch_p, f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 2)), witch_ang + math.pi / 2, bank))
    # cape ondule
    cape_obj = bpy.data.objects.get("cape_p")
    if cape_obj:
        kf(cape_obj, f, "rotation_euler", (math.radians(15 * math.sin(2 * math.pi * tt * 4)), 0, math.radians(8 * math.cos(2 * math.pi * tt * 5))))

    # chimney smoke rise
    for sm in chim_smokes:
        ph = sm["_phase"]
        local = (tt * 1.3 + ph) % 1.0
        ny = 1.80 + local * 2.5
        sc = 1.0 + local * 1.2
        kf(sm, f, "location", (0, ny, 0))
        kf(sm, f, "scale", (sc, sc, sc))

    # cauldron bubbles pulse + steam rise + fire pulse
    for cb in caul_bubs:
        ph = cb["_phase"]
        pulse = 1.0 + 0.6 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(cb, f, "scale", (pulse, pulse * 0.7, pulse))
    for st in caul_steams:
        ph = st["_phase"]
        local = (tt * 1.0 + ph) % 1.0
        ny = 1.20 + local * 1.8
        sc = 1.0 + local * 1.0
        kf(st, f, "location", (0, ny, 0))
        kf(st, f, "scale", (sc, sc, sc))
    cf = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 5)
    kf(caul_fire, f, "scale", (cf, cf * 0.85, cf))
    # liquid pulse
    lq = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 3)
    kf(liquid, f, "scale", (lq, 0.2 * (1 + 0.1 * math.sin(2 * math.pi * tt * 3)), lq))

    # 6 pumpkins pulse + sway
    for pi, pp in enumerate(pumpkins):
        ph = pp["_phase"]
        ps = 1.0 + 0.08 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(pp, f, "scale", (ps, ps, ps))

    # 8 ravens : flap occasional + dart
    for rv in ravens:
        ph = rv["phase"]
        # occasional flap (peaks every 1.5s)
        flap_intensity = math.exp(-((tt + ph * 0.2) % 0.5) * 6) if ((tt + ph * 0.2) % 0.5) < 0.15 else 0
        wflap = math.radians(40) * flap_intensity * math.sin(2 * math.pi * tt * 8 + ph * math.pi)
        kf(rv["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(rv["wR"], f, "rotation_euler", (-wflap, 0, 0))
        # head turn slight
        kf(rv["p"], f, "rotation_euler", (0, math.radians(10 * math.sin(2 * math.pi * tt * 0.7 + ph)), 0))

    # 30 fireflies : spiral upward
    for fp_obj in fireflies:
        a0 = fp_obj["_a"]
        r0 = fp_obj["_r0"]
        y0 = fp_obj["_y0"]
        ph = fp_obj["_phase"]
        spiral_ang = a0 + tt * 2 * math.pi * 0.8
        spiral_r = r0 + 0.4 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi)
        ny = y0 + 0.6 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        nx = math.cos(spiral_ang) * spiral_r
        nz = math.sin(spiral_ang) * spiral_r
        kf(fp_obj, f, "location", (nx, ny, nz))
        sc = 0.6 + 0.5 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(fp_obj, f, "scale", (sc, sc, sc))

    # 10 fog puffs drift
    for fp in fog_puffs:
        bx_ = fp["_base_x"]
        ph = fp["_phase"]
        nx = bx_ + 0.8 * math.sin(2 * math.pi * tt * 0.4 + ph * math.pi)
        sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        kf(fp, f, "location", (nx, fp.location.y if f > 1 else fp.location.y, fp.location.z if f > 1 else fp.location.z))
        kf(fp, f, "scale", (sc, 0.15, sc))

    # grimoire float + page turn
    gx = -3 + 0.2 * math.sin(2 * math.pi * tt * 0.8)
    gy = 1.5 + 0.30 * math.sin(2 * math.pi * tt * 1.5)
    kf(grimoire_p, f, "location", (gx, gy, 3.5))
    kf(grimoire_p, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 0.5)), 0))
    # page turning (rotation Y)
    page_rot = math.radians(180) * (1 - math.cos(2 * math.pi * tt * 1.0)) / 2
    kf(turning_page, f, "rotation_euler", (0, 0, page_rot))

    # 5 trees sway léger
    for ti, tp in enumerate(trees):
        sw = math.radians(2) * math.sin(2 * math.pi * tt * 0.5 + ti * 0.5)
        kf(tp, f, "rotation_euler", (sw, 0, math.radians(1.5 * math.cos(2 * math.pi * tt * 0.6 + ti * 0.4))))

    # moon halos breathe
    mh1 = 1.0 + 0.08 * math.sin(2 * math.pi * tt * 1.3)
    mh2 = 1.0 + 0.10 * math.cos(2 * math.pi * tt * 1.1)
    kf(moon_halo_1, f, "scale", (mh1, mh1, mh1))
    kf(moon_halo_2, f, "scale", (mh2, mh2, mh2))

    # 6 windows pulse subtle
    for wi, win in enumerate(window_objects):
        ws = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 2 + wi * 0.5)
        kf(win, f, "scale", (ws, ws, ws))

    # cat tail wave
    kf(tail_p, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 1.5)), math.radians(15 * math.cos(2 * math.pi * tt * 1.2))))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_witch_cottage_forest] wrote {OUT}")
