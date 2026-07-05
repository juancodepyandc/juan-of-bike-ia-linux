"""
proc_pyramid_egypt.py — 116e procédural AuroraIA, Phase F++++.

Pyramide de Khéops avec Sphinx : pyramide principale en gradins
(15 niveaux décroissants) + sphinx couché (corps + tête + couronne) + 4 mini-
pyramides reines + 2 obélisques avec hiéroglyphes + 4 palmiers oasis
+ chameau + dune sable + ciel coucher de soleil + soleil disque rouge
+ 5 oiseaux + 3 cactus + ouverture de la pyramide.

Animation :
- 4 palmiers : sway feuilles
- chameau : marche subtle bob + tilt
- 5 oiseaux : volent en arcs
- soleil : pulse + halo
- sable : subtle wave
- obelisks : pas d'anim mais structure complexe

Sortie : output/3d/pbr_pyramid_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_pyramid_proc.glb"))

random.seed(0xE6FBE5)

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


def cube(name, size=1.0, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def sphere(name, r=1.0, segs=24, rings=12, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY_SUNSET = make_mat("sky_sunset", (0.95, 0.55, 0.30), roughness=1.0,
                            emi=(0.95, 0.55, 0.25), emi_strength=0.8)
MAT_SKY_GRADIENT = make_mat("sky_grad", (0.55, 0.30, 0.45), roughness=1.0,
                              emi=(0.55, 0.30, 0.45), emi_strength=0.5)
MAT_SUN = make_mat("sun", (1.0, 0.45, 0.20), roughness=0.0,
                    emi=(1.0, 0.45, 0.20), emi_strength=7.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.55, 0.25), roughness=0.0, alpha=0.3,
                          emi=(1.0, 0.55, 0.25), emi_strength=3.0)
MAT_SAND = make_mat("sand", (0.92, 0.78, 0.50), roughness=0.95)
MAT_SAND_DARK = make_mat("sand_dark", (0.70, 0.55, 0.30), roughness=0.95)
MAT_LIMESTONE = make_mat("limestone", (0.90, 0.80, 0.55), roughness=0.85)
MAT_LIMESTONE_DARK = make_mat("limestone_dark", (0.75, 0.62, 0.40), roughness=0.85)
MAT_GOLD = make_mat("gold_cap", (1.0, 0.85, 0.30), metallic=0.95, roughness=0.15,
                     emi=(0.6, 0.45, 0.10), emi_strength=0.6)
MAT_SPHINX = make_mat("sphinx", (0.85, 0.70, 0.45), roughness=0.85)
MAT_OBELISK = make_mat("obelisk", (0.85, 0.70, 0.40), roughness=0.7,
                         emi=(0.30, 0.20, 0.10), emi_strength=0.2)
MAT_HIEROGLYPH = make_mat("hieroglyph", (0.30, 0.20, 0.10), roughness=0.5,
                            emi=(0.3, 0.15, 0.05), emi_strength=0.3)
MAT_PALM_TRUNK = make_mat("palm_trunk", (0.35, 0.25, 0.15), roughness=0.9)
MAT_PALM_LEAF = make_mat("palm_leaf", (0.20, 0.45, 0.15), roughness=0.85)
MAT_OASIS_WATER = make_mat(
    "oasis_water", (0.15, 0.55, 0.65), metallic=0.7, roughness=0.1, alpha=0.85,
    emi=(0.25, 0.65, 0.75), emi_strength=0.8,
)
MAT_CAMEL_BODY = make_mat("camel", (0.75, 0.55, 0.30), roughness=0.85)
MAT_CAMEL_HUMP = make_mat("camel_hump", (0.65, 0.45, 0.22), roughness=0.85)
MAT_BIRD = make_mat("bird", (0.20, 0.15, 0.10), roughness=0.7)
MAT_CACTUS = make_mat("cactus", (0.20, 0.45, 0.20), roughness=0.85)
MAT_PYRAMID_ENTRANCE = make_mat("entrance", (0.05, 0.04, 0.03), roughness=0.6,
                                  emi=(0.40, 0.20, 0.05), emi_strength=0.5)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY_SUNSET)
sky.scale = (32, 0.1, 14)

# upper sky band (purple)
sky_up = cube("sky_upper", size=1.0, loc=(0, 18, 11), mat=MAT_SKY_GRADIENT)
sky_up.scale = (32, 0.1, 6)

# sun setting at horizon
sun_p = empty("sun_p", (4.0, 15.0, 4.5))
sun = sphere("sun", r=1.5, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo = sphere("sun_halo", r=2.8, segs=24, rings=16, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# --- desert ground ---------------------------------------------------------
ground = cube("desert", size=1.0, loc=(0, -0.05, 0), mat=MAT_SAND)
ground.scale = (40, 0.1, 28)

# 4 dunes (subtle elevations)
for i, (dx, dz, dsx, dsz) in enumerate([(-10, 2, 6, 3), (12, -3, 5, 2.5), (-15, -5, 4, 3), (15, 5, 5, 3)]):
    d = sphere(f"dune_{i}", r=2.0, segs=16, rings=10, loc=(dx, 0, dz), mat=MAT_SAND_DARK)
    d.scale = (dsx, 0.6, dsz)

# --- main pyramid : 15 stepped tiers ---------------------------------------
pyramid_p = empty("pyramid", (-3.0, 0, -3.0))
N_TIERS = 15
TIER_BASE = 6.0
TIER_HEIGHT = 0.55
for i in range(N_TIERS):
    t = i / (N_TIERS - 1)
    size = TIER_BASE * (1.0 - t * 0.94)
    y = TIER_HEIGHT * (i + 0.5)
    mat = MAT_LIMESTONE_DARK if i % 2 == 1 else MAT_LIMESTONE
    tier = cube(f"pyramid_tier_{i}", size=1.0, loc=(0, y, 0), parent=pyramid_p, mat=mat)
    tier.scale = (size, TIER_HEIGHT, size)

# gold capstone on top
cap = cone("pyramid_cap", r1=0.3, r2=0.0, depth=0.6, segs=4, loc=(0, TIER_HEIGHT * N_TIERS + 0.3, 0), parent=pyramid_p, mat=MAT_GOLD)
cap.rotation_euler = (math.radians(90), 0, math.radians(45))

# entrance (dark rectangle on north face)
entrance = cube("entrance", size=1.0, loc=(0, 1.2, 3.0), parent=pyramid_p, mat=MAT_PYRAMID_ENTRANCE)
entrance.scale = (0.6, 0.8, 0.05)

# --- 4 queen pyramids ------------------------------------------------------
for i, (px, pz, ps) in enumerate([(-12, -3, 1.5), (-11, -5, 1.2), (-10, -7, 1.0), (-9.5, -9, 0.8)]):
    qp = empty(f"queen_{i}", (px, 0, pz))
    for j in range(8):
        t = j / 7
        size = ps * 2.0 * (1 - t * 0.9)
        y = 0.3 * (j + 0.5)
        tier = cube(f"queen_{i}_t{j}", size=1.0, loc=(0, y, 0), parent=qp, mat=MAT_LIMESTONE)
        tier.scale = (size, 0.3, size)

# --- sphinx couché --------------------------------------------------------
sphinx_p = empty("sphinx", (4.0, 0, 4.0))
sphinx_p.rotation_euler = (0, math.radians(-30), 0)

# body (long block)
body = cube("sphinx_body", size=1.0, loc=(0, 0.8, 0), parent=sphinx_p, mat=MAT_SPHINX)
body.scale = (3.5, 0.8, 1.2)

# 4 paws (extended forward)
for i, (px, pz) in enumerate([(2.5, 0.4), (2.5, -0.4), (-1.5, 0.6), (-1.5, -0.6)]):
    paw = cube(f"sphinx_paw_{i}", size=1.0, loc=(px, 0.3, pz), parent=sphinx_p, mat=MAT_SPHINX)
    paw.scale = (1.0, 0.3, 0.35)

# head (sits at front)
head_p = empty("sphinx_head", (2.5, 1.6, 0), parent=sphinx_p)
head = cube("sphinx_head_box", size=1.0, loc=(0, 0, 0), parent=head_p, mat=MAT_SPHINX)
head.scale = (0.8, 0.9, 0.8)

# nemes headdress (striped)
nemes = cube("nemes", size=1.0, loc=(0, 0.4, 0), parent=head_p, mat=MAT_GOLD)
nemes.scale = (0.85, 0.5, 0.85)

# face features
nose = cone("nose", r1=0.08, r2=0.05, depth=0.15, segs=4, loc=(0.4, 0.05, 0), parent=head_p, mat=MAT_SPHINX)
nose.rotation_euler = (0, math.radians(90), 0)

# eyes
for dy_z in [(0.10, 0.20), (0.10, -0.20)]:
    eye = sphere(f"sphinx_eye_{dy_z[1]}", r=0.05, segs=8, rings=6, loc=(0.42, dy_z[0], dy_z[1]), parent=head_p, mat=MAT_HIEROGLYPH)

# tail (curled)
tail = cone("sphinx_tail", r1=0.10, r2=0.03, depth=1.5, segs=6, loc=(-2.0, 0.6, 0), parent=sphinx_p, mat=MAT_SPHINX)
tail.rotation_euler = (math.radians(70), math.radians(20), 0)

# --- 2 obelisks ------------------------------------------------------------
def make_obelisk(name, x, z, height=3.5):
    op = empty(name, (x, 0, z))
    base = cube(f"{name}_base", size=1.0, loc=(0, 0.15, 0), parent=op, mat=MAT_LIMESTONE_DARK)
    base.scale = (0.7, 0.3, 0.7)
    # main shaft (tall slim)
    shaft = cone(f"{name}_shaft", r1=0.35, r2=0.18, depth=height, segs=4, loc=(0, height / 2 + 0.3, 0), parent=op, mat=MAT_OBELISK)
    shaft.rotation_euler = (math.radians(90), 0, math.radians(45))
    # gold pyramidion on top
    pyr = cone(f"{name}_top", r1=0.20, r2=0.0, depth=0.4, segs=4, loc=(0, height + 0.3 + 0.2, 0), parent=op, mat=MAT_GOLD)
    pyr.rotation_euler = (math.radians(90), 0, math.radians(45))
    # 8 hieroglyph patches on the shaft
    for i in range(8):
        ya = 1.0 + i * 0.35
        h = cube(f"{name}_hier_{i}", size=1.0, loc=(0.18, ya, 0), parent=op, mat=MAT_HIEROGLYPH)
        h.scale = (0.02, 0.15, 0.15)
    return op

ob1 = make_obelisk("obelisk_1", 6.5, -2.0)
ob2 = make_obelisk("obelisk_2", 9.0, -1.0)

# --- 4 palmiers oasis ------------------------------------------------------
palms = []
def make_palm(name, x, z, scale=1.0):
    pp = empty(name, (x, 0, z))
    # trunk (curved : 5 segments)
    trunk_p = empty(f"{name}_trunk_p", (0, 0, 0), parent=pp)
    for i in range(5):
        h = 0.5 + i * 0.8
        cone_seg = cone(f"{name}_trunk_{i}", r1=0.18 * scale - i * 0.015, r2=0.16 * scale - i * 0.015, depth=0.8 * scale, segs=8,
                          loc=(math.sin(i * 0.3) * 0.1, h, 0), parent=trunk_p, mat=MAT_PALM_TRUNK)
        cone_seg.rotation_euler = (math.radians(90), 0, 0)
    # leaves head (8 fronds radiating)
    head = empty(f"{name}_leaves", (0, 4.2 * scale, 0), parent=pp)
    for j in range(8):
        a = j * (math.pi * 2 / 8)
        # frond is a stretched ellipse
        frond = sphere(f"{name}_frond_{j}", r=0.3, segs=10, rings=6, loc=(math.cos(a) * 0.8, -0.1, math.sin(a) * 0.8), parent=head, mat=MAT_PALM_LEAF)
        frond.scale = (3.5, 0.3, 0.6)
        frond.rotation_euler = (math.radians(-15), -a, 0)
    # 3 coconuts at the head
    for k in range(3):
        coco = sphere(f"{name}_coco_{k}", r=0.1, segs=10, rings=8, loc=(math.cos(k * 2) * 0.15, 4.0 * scale, math.sin(k * 2) * 0.15), parent=pp, mat=MAT_PALM_TRUNK)
    return pp, head

for i, (x, z, sc) in enumerate([(10, 3, 1.0), (12, 5, 1.1), (8, 6, 0.9), (11, 1, 1.0)]):
    p, head = make_palm(f"palm_{i}", x, z, sc)
    palms.append(head)

# --- oasis water pond at the palms -----------------------------------------
oasis = cube("oasis_pond", size=1.0, loc=(10.5, 0.02, 4.0), mat=MAT_OASIS_WATER)
oasis.scale = (2.0, 0.05, 1.5)

# --- chameau ---------------------------------------------------------------
camel_p = empty("camel", (0.5, 0.45, 5.5))
camel_p.rotation_euler = (0, math.radians(-20), 0)
body = cube("camel_body", size=1.0, loc=(0, 0.5, 0), parent=camel_p, mat=MAT_CAMEL_BODY)
body.scale = (1.2, 0.4, 0.5)
# 2 humps
hump1 = sphere("camel_hump1", r=0.3, segs=14, rings=10, loc=(0.25, 0.95, 0), parent=camel_p, mat=MAT_CAMEL_HUMP)
hump1.scale = (1.0, 1.0, 1.0)
hump2 = sphere("camel_hump2", r=0.25, segs=12, rings=10, loc=(-0.30, 0.90, 0), parent=camel_p, mat=MAT_CAMEL_HUMP)
hump2.scale = (1.0, 1.0, 1.0)
# neck (cone going up)
neck = cone("camel_neck", r1=0.18, r2=0.15, depth=0.7, segs=8, loc=(0.7, 0.95, 0), parent=camel_p, mat=MAT_CAMEL_BODY)
neck.rotation_euler = (0, 0, math.radians(-30))
# head
head = sphere("camel_head", r=0.20, segs=12, rings=10, loc=(0.95, 1.25, 0), parent=camel_p, mat=MAT_CAMEL_BODY)
head.scale = (1.4, 0.9, 0.8)
# 4 legs
for i, (lx, lz) in enumerate([(0.5, 0.3), (0.5, -0.3), (-0.5, 0.3), (-0.5, -0.3)]):
    leg = cube(f"camel_leg_{i}", size=1.0, loc=(lx, 0.15, lz), parent=camel_p, mat=MAT_CAMEL_BODY)
    leg.scale = (0.15, 0.40, 0.15)

# --- 5 oiseaux flying ------------------------------------------------------
birds = []
for i in range(5):
    a = i * (math.pi * 2 / 5) + 0.3
    r = 4.5
    bx = math.cos(a) * r + 2
    bz = math.sin(a) * r
    by = 9.0 + random.uniform(-0.5, 0.5)
    bp = empty(f"bird_{i}", (bx, by, bz))
    body = sphere(f"bird_{i}_body", r=0.12, segs=8, rings=6, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD)
    body.scale = (1.5, 0.7, 1.0)
    for side, xx in (("L", -0.3), ("R", 0.3)):
        w = cube(f"bird_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=bp, mat=MAT_BIRD)
        w.scale = (0.25, 0.02, 0.10)
    birds.append((bp, a, r, by))

# --- 3 cacti scattered -----------------------------------------------------
for i, (cx, cz) in enumerate([(-8, 5), (15, 0), (-4, 8)]):
    cp = empty(f"cactus_{i}", (cx, 0, cz))
    main = cone(f"cactus_{i}_main", r1=0.25, r2=0.20, depth=1.4, segs=12, loc=(0, 0.7, 0), parent=cp, mat=MAT_CACTUS)
    main.rotation_euler = (math.radians(90), 0, 0)
    # 2 arms
    for j, (ax, ay, az, rot) in enumerate([(0.30, 0.7, 0, math.radians(-60)), (-0.30, 0.9, 0, math.radians(60))]):
        a = cone(f"cactus_{i}_arm_{j}", r1=0.15, r2=0.12, depth=0.6, segs=10, loc=(ax, ay, az), parent=cp, mat=MAT_CACTUS)
        a.rotation_euler = (math.radians(90), 0, rot)

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

# palms sway (rotate leaves head)
for i, palm_head in enumerate(palms):
    phase = i * 0.7
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(6) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(palm_head, f, (bend, 0, bend * 0.5))

# camel walk : subtle bob + slight forward translation
cx0 = camel_p.location.x
cy0 = camel_p.location.y
cz0 = camel_p.location.z
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    dy = cy0 + 0.05 * math.sin(tt * math.pi * 8.0)
    dx = cx0 + tt * 1.5
    tilt = math.radians(3) * math.sin(tt * math.pi * 8.0)
    kf_loc(camel_p, f, (dx, dy, cz0))
    kf_rot(camel_p, f, (tilt, math.radians(-20), 0))

# birds fly in arcs
for bp, a0, r, by in birds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r + 2
        bz = math.sin(angle) * r
        by_a = by + 0.3 * math.sin(tt * math.pi * 4.0 + a0 * 2)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 8.0)))

# sun halo breathe
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.10 * math.sin(tt * math.pi * 3.0)
    kf_scale(sun_halo, f, (s, s, s))
    # sun small pulse
    sp = 1.0 + 0.05 * math.sin(tt * math.pi * 5.0)
    kf_scale(sun, f, (sp, sp, sp))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_pyramid] wrote {OUT}")
