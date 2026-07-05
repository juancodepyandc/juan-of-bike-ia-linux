"""
proc_savanna_safari.py — 135e procédural AuroraIA, Phase F++++.

Savane africaine au lever du soleil : sol terre rouge + herbes hautes
+ 3 acacias parasol + 2 éléphants (grand + bébé) + 3 girafes hautes
+ 4 zèbres + 1 lion + 1 lionne + 6 oiseaux + 2 rochers énormes
+ 3 buissons + 1 plateau rocher + ciel matin doré + soleil émissif
+ 8 termitières.

Animation :
- animaux head bob
- 30 herbes sway
- 6 oiseaux orbites
- lion mouvement queue
- soleil halo pulse

Sortie : output/3d/pbr_savanna_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_savanna_proc.glb"))

random.seed(0xCAFE83)

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
MAT_SKY = make_mat("sky_dawn", (1.0, 0.75, 0.40), roughness=1.0,
                    emi=(0.95, 0.65, 0.30), emi_strength=0.7)
MAT_SKY_TOP = make_mat("sky_top", (0.75, 0.55, 0.30), roughness=1.0,
                         emi=(0.65, 0.45, 0.25), emi_strength=0.5)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.45), roughness=0.0,
                    emi=(1.0, 0.85, 0.45), emi_strength=8.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.80, 0.40), roughness=0.0, alpha=0.30,
                          emi=(1.0, 0.75, 0.35), emi_strength=3.0)
MAT_GROUND = make_mat("ground_red", (0.65, 0.40, 0.20), roughness=0.95)
MAT_GROUND_GRASS = make_mat("ground_grass", (0.55, 0.50, 0.25), roughness=0.9)
MAT_GRASS = make_mat("grass", (0.75, 0.65, 0.30), roughness=0.85,
                       emi=(0.30, 0.25, 0.10), emi_strength=0.2)
MAT_ACACIA_TRUNK = make_mat("acacia_trunk", (0.30, 0.20, 0.12), roughness=0.9)
MAT_ACACIA_LEAVES = make_mat("acacia_leaves", (0.25, 0.45, 0.20), roughness=0.85,
                               emi=(0.08, 0.20, 0.08), emi_strength=0.3)
MAT_ELEPHANT = make_mat("elephant", (0.45, 0.42, 0.40), roughness=0.85)
MAT_ELEPHANT_TUSK = make_mat("elephant_tusk", (0.95, 0.92, 0.85), roughness=0.5,
                               emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_ELEPHANT_EAR = make_mat("elephant_ear", (0.40, 0.38, 0.36), roughness=0.85)
MAT_GIRAFFE = make_mat("giraffe", (0.85, 0.65, 0.30), roughness=0.7)
MAT_GIRAFFE_SPOT = make_mat("giraffe_spot", (0.40, 0.20, 0.10), roughness=0.7)
MAT_ZEBRA_WHITE = make_mat("zebra_white", (0.92, 0.90, 0.85), roughness=0.7)
MAT_ZEBRA_BLACK = make_mat("zebra_black", (0.10, 0.08, 0.06), roughness=0.7)
MAT_LION_BODY = make_mat("lion_body", (0.75, 0.55, 0.25), roughness=0.7)
MAT_LION_MANE = make_mat("lion_mane", (0.55, 0.30, 0.15), roughness=0.8)
MAT_LIONESS = make_mat("lioness", (0.80, 0.60, 0.30), roughness=0.7)
MAT_BIRD = make_mat("bird", (0.35, 0.25, 0.15), roughness=0.7)
MAT_ROCK = make_mat("rock", (0.50, 0.42, 0.32), roughness=0.95)
MAT_BUSH = make_mat("bush", (0.30, 0.45, 0.20), roughness=0.85)
MAT_TERMITE = make_mat("termite", (0.55, 0.35, 0.20), roughness=0.9)
MAT_EYE_BLACK = make_mat("eye_black", (0.05, 0.05, 0.05), roughness=0.3)

# --- backdrop : dawn sky --------------------------------------------------
sky_top = cube("sky_top", size=1.0, loc=(0, 18, 11), mat=MAT_SKY_TOP)
sky_top.scale = (40, 0.1, 8)
sky_bot = cube("sky_dawn", size=1.0, loc=(0, 18, 4), mat=MAT_SKY)
sky_bot.scale = (40, 0.1, 8)

# sun + halo
sun_p = empty("sun_p", (10.0, 12.0, 8.5))
sun = sphere("sun", r=1.5, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo = sphere("sun_halo", r=2.8, segs=22, rings=16, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# --- savanna ground --------------------------------------------------------
ground = cube("ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_GROUND)
ground.scale = (35, 0.1, 25)

# yellowish grass patches
for i in range(6):
    gx = random.uniform(-12, 12)
    gz = random.uniform(-9, 9)
    g = cube(f"grass_patch_{i}", size=1.0, loc=(gx, 0.01, gz), mat=MAT_GROUND_GRASS)
    g.scale = (random.uniform(1.8, 3.5), 0.05, random.uniform(1.4, 2.5))

# 30 grass tufts (tall stalks)
grass_tufts = []
for i in range(30):
    gx = random.uniform(-12, 12)
    gz = random.uniform(-9, 9)
    gp = empty(f"grass_t_{i}", (gx, 0, gz))
    # 4 blade-like cones
    for k in range(4):
        ka = k * (math.pi / 4)
        h = random.uniform(0.4, 0.8)
        blade = cone(f"grass_{i}_{k}", r1=0.04, r2=0.01, depth=h, segs=4, loc=(math.cos(ka) * 0.06, h / 2, math.sin(ka) * 0.06), parent=gp, mat=MAT_GRASS)
        blade.rotation_euler = (math.radians(90), 0, ka)
    grass_tufts.append((gp, i))

# --- 3 acacias parasol ----------------------------------------------------
def make_acacia(name, x, z, scale=1.0):
    p = empty(name, (x, 0, z))
    # trunk (3 segments slightly curving)
    for j in range(3):
        sx = math.sin(j * 0.4) * 0.15
        h = 0.4 + j * 0.8
        tr = cone(f"{name}_t_{j}", r1=0.28 - j * 0.04, r2=0.25 - j * 0.04, depth=0.8, segs=8, loc=(sx, h, 0), parent=p, mat=MAT_ACACIA_TRUNK)
        tr.rotation_euler = (math.radians(90), 0, 0)
    # parasol canopy (flat wide foliage layer)
    canopy_p = empty(f"{name}_canopy", (0, 3.0, 0), parent=p)
    # 7 leaf clusters spread horizontally
    for k in range(7):
        ka = k * (math.pi * 2 / 7)
        clr = scale * 2.0
        if k == 6:  # center one
            cx = 0
            cz = 0
            cr = 1.5
        else:
            cx = math.cos(ka) * clr
            cz = math.sin(ka) * clr
            cr = 1.2
        cl = sphere(f"{name}_l_{k}", r=cr, segs=14, rings=8, loc=(cx, 0, cz), parent=canopy_p, mat=MAT_ACACIA_LEAVES)
        cl.scale = (1.0, 0.30, 1.0)
    return p, canopy_p

acacia_canopies = []
for i, (ax, az, asc) in enumerate([(-8, 5, 1.0), (8, 4, 1.1), (-4, 8, 0.9)]):
    p, canopy = make_acacia(f"acacia_{i}", ax, az, asc)
    acacia_canopies.append(canopy)

# --- 2 éléphants (grand + bébé) ---------------------------------------
def make_elephant(name, x, z, scale=1.0, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    # body (large oval)
    body = sphere(f"{name}_body", r=0.7 * scale, segs=18, rings=12, loc=(0, 1.0 * scale, 0), parent=p, mat=MAT_ELEPHANT)
    body.scale = (1.8, 0.9, 1.0)
    # head
    head_p = empty(f"{name}_head_p", (1.25 * scale, 1.1 * scale, 0), parent=p)
    head = sphere(f"{name}_head", r=0.45 * scale, segs=14, rings=10, loc=(0, 0, 0), parent=head_p, mat=MAT_ELEPHANT)
    head.scale = (1.1, 1.0, 0.9)
    # 2 ears (large flat squashed spheres)
    for side, dz in [("L", 0.40), ("R", -0.40)]:
        ear = sphere(f"{name}_ear_{side}", r=0.40 * scale, segs=12, rings=8, loc=(0, 0.10 * scale, dz), parent=head_p, mat=MAT_ELEPHANT_EAR)
        ear.scale = (0.3, 0.9, 1.4)
    # 2 small eyes
    for side, dz in [("L", 0.18), ("R", -0.18)]:
        eye = sphere(f"{name}_eye_{side}", r=0.05 * scale, segs=8, rings=6, loc=(0.30 * scale, 0.10, dz), parent=head_p, mat=MAT_EYE_BLACK)
    # trunk (4 segments curving down)
    trunk_p = empty(f"{name}_trunk_p", (0.45 * scale, -0.10, 0), parent=head_p)
    for j in range(4):
        sx = j * 0.20
        sy = -j * 0.20
        sd = 0.15 - j * 0.03
        seg = cone(f"{name}_tr_{j}", r1=sd * scale, r2=(sd - 0.02) * scale, depth=0.30 * scale, segs=8, loc=(sx * scale, sy * scale, 0), parent=trunk_p, mat=MAT_ELEPHANT)
        seg.rotation_euler = (0, math.radians(45 + j * 10), 0)
    # 2 tusks (on each side of trunk)
    for side, dz in [("L", 0.15), ("R", -0.15)]:
        tusk = cone(f"{name}_tusk_{side}", r1=0.04 * scale, r2=0.01 * scale, depth=0.30 * scale, segs=6, loc=(0.40 * scale, -0.10, dz), parent=head_p, mat=MAT_ELEPHANT_TUSK)
        tusk.rotation_euler = (math.radians(-15), math.radians(80), 0)
    # 4 legs (pillar-like cylinders)
    for k, (lx, lz) in enumerate([(0.55, 0.35), (0.55, -0.35), (-0.55, 0.35), (-0.55, -0.35)]):
        leg = cube(f"{name}_leg_{k}", size=1.0, loc=(lx * scale, 0.40 * scale, lz * scale), parent=p, mat=MAT_ELEPHANT)
        leg.scale = (0.20 * scale, 0.80 * scale, 0.20 * scale)
    # tail
    tail = cone(f"{name}_tail", r1=0.05 * scale, r2=0.02 * scale, depth=0.40 * scale, segs=6, loc=(-1.0 * scale, 0.90 * scale, 0), parent=p, mat=MAT_ELEPHANT)
    tail.rotation_euler = (0, 0, math.radians(110))
    return p, head_p

elephant_heads = []
big_el, big_head = make_elephant("elephant_big", -2.0, 2.0, 1.4, math.radians(-30))
elephant_heads.append(big_head)
baby_el, baby_head = make_elephant("elephant_baby", -1.0, 3.5, 0.7, math.radians(20))
elephant_heads.append(baby_head)

# --- 3 girafes hautes ---------------------------------------------------
def make_giraffe(name, x, z, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    # body
    body = sphere(f"{name}_body", r=0.55, segs=16, rings=10, loc=(0, 2.0, 0), parent=p, mat=MAT_GIRAFFE)
    body.scale = (1.6, 0.9, 0.9)
    # spots on body
    for k in range(5):
        ka = k * (math.pi * 2 / 5)
        sx = math.cos(ka) * 0.4
        sz = math.sin(ka) * 0.4
        sp_obj = sphere(f"{name}_spot_b_{k}", r=0.15, segs=8, rings=6, loc=(sx, 2.0 + math.sin(ka) * 0.2, sz), parent=p, mat=MAT_GIRAFFE_SPOT)
        sp_obj.scale = (1.0, 0.3, 1.0)
    # long neck (5 segments)
    neck_p = empty(f"{name}_neck_p", (0.5, 2.4, 0), parent=p)
    for j in range(5):
        sx = 0.10
        sy = j * 0.45
        seg = cone(f"{name}_neck_{j}", r1=0.20 - j * 0.012, r2=0.18 - j * 0.012, depth=0.45, segs=8, loc=(sx, sy + 0.22, 0), parent=neck_p, mat=MAT_GIRAFFE)
        seg.rotation_euler = (0, 0, math.radians(-15))
        # 1 spot per segment
        sp_obj = sphere(f"{name}_neck_sp_{j}", r=0.08, segs=8, rings=6, loc=(sx + 0.10, sy + 0.22, 0), parent=neck_p, mat=MAT_GIRAFFE_SPOT)
        sp_obj.scale = (1.0, 0.3, 1.0)
    # head
    head_p = empty(f"{name}_head_p", (0.7, 5.0, 0), parent=p)
    head = sphere(f"{name}_head", r=0.25, segs=12, rings=8, loc=(0, 0, 0), parent=head_p, mat=MAT_GIRAFFE)
    head.scale = (1.6, 0.9, 0.8)
    # 2 ears
    for side, dz in [("L", 0.18), ("R", -0.18)]:
        ear = cone(f"{name}_ear_{side}", r1=0.06, r2=0.02, depth=0.15, segs=6, loc=(-0.10, 0.20, dz), parent=head_p, mat=MAT_GIRAFFE)
        ear.rotation_euler = (math.radians(-20), 0, math.radians(15 if side == "L" else -15))
    # 2 ossicones (small horns)
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        osc = cone(f"{name}_osc_{side}", r1=0.04, r2=0.02, depth=0.20, segs=6, loc=(-0.05, 0.30, dz), parent=head_p, mat=MAT_GIRAFFE_SPOT)
        osc.rotation_euler = (math.radians(-10), 0, 0)
    # eyes
    for side, dz in [("L", 0.13), ("R", -0.13)]:
        eye = sphere(f"{name}_eye_{side}", r=0.03, segs=8, rings=6, loc=(0.15, 0.08, dz), parent=head_p, mat=MAT_EYE_BLACK)
    # 4 long legs
    for k, (lx, lz) in enumerate([(0.45, 0.25), (0.45, -0.25), (-0.45, 0.25), (-0.45, -0.25)]):
        leg = cube(f"{name}_leg_{k}", size=1.0, loc=(lx, 1.0, lz), parent=p, mat=MAT_GIRAFFE)
        leg.scale = (0.10, 2.0, 0.10)
    # tail
    tail = cone(f"{name}_tail", r1=0.04, r2=0.01, depth=0.40, segs=6, loc=(-0.85, 1.95, 0), parent=p, mat=MAT_GIRAFFE)
    tail.rotation_euler = (0, 0, math.radians(110))
    return p, head_p, neck_p

giraffe_objs = []
for i, (gx, gz, grot) in enumerate([(3, 5, math.radians(45)), (5, 6, math.radians(-30)), (-5, 6.5, math.radians(60))]):
    gp, head_p, neck_p = make_giraffe(f"giraffe_{i}", gx, gz, grot)
    giraffe_objs.append((gp, head_p, neck_p))

# --- 4 zèbres ---------------------------------------------------------
def make_zebra(name, x, z, rot=0):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, rot, 0)
    body = sphere(f"{name}_body", r=0.40, segs=14, rings=10, loc=(0, 0.85, 0), parent=p, mat=MAT_ZEBRA_WHITE)
    body.scale = (1.7, 0.8, 0.7)
    # 5 black stripes on body
    for k in range(5):
        kx = -0.5 + k * 0.25
        stripe = cube(f"{name}_str_{k}", size=1.0, loc=(kx, 0.85, 0), parent=p, mat=MAT_ZEBRA_BLACK)
        stripe.scale = (0.06, 0.45, 0.55)
    # head
    head_p = empty(f"{name}_head_p", (0.55, 1.0, 0), parent=p)
    head = sphere(f"{name}_head", r=0.18, segs=12, rings=8, loc=(0, 0, 0), parent=head_p, mat=MAT_ZEBRA_WHITE)
    head.scale = (1.4, 0.9, 0.8)
    # 2 ears
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        ear = cone(f"{name}_ear_{side}", r1=0.04, r2=0.0, depth=0.10, segs=6, loc=(-0.10, 0.18, dz), parent=head_p, mat=MAT_ZEBRA_WHITE)
        ear.rotation_euler = (math.radians(-20), 0, 0)
    # snout
    snout = sphere(f"{name}_snout", r=0.10, segs=10, rings=6, loc=(0.18, -0.05, 0), parent=head_p, mat=MAT_ZEBRA_BLACK)
    # 4 legs
    for k, (lx, lz) in enumerate([(0.45, 0.20), (0.45, -0.20), (-0.45, 0.20), (-0.45, -0.20)]):
        leg = cube(f"{name}_leg_{k}", size=1.0, loc=(lx, 0.40, lz), parent=p, mat=MAT_ZEBRA_WHITE)
        leg.scale = (0.08, 0.8, 0.08)
        # stripe on leg
        ls = cube(f"{name}_leg_str_{k}", size=1.0, loc=(lx, 0.50, lz), parent=p, mat=MAT_ZEBRA_BLACK)
        ls.scale = (0.09, 0.06, 0.09)
    # tail
    tail = cone(f"{name}_tail", r1=0.04, r2=0.02, depth=0.30, segs=6, loc=(-0.75, 0.85, 0), parent=p, mat=MAT_ZEBRA_BLACK)
    tail.rotation_euler = (0, 0, math.radians(110))
    return p, head_p

zebra_heads = []
for i, (zx, zz, zrot) in enumerate([
    (-3, -3, math.radians(-20)),
    (-2, -4, math.radians(15)),
    (-4, -4.5, math.radians(-40)),
    (-2.5, -5.5, math.radians(45)),
]):
    zp, head_p = make_zebra(f"zebra_{i}", zx, zz, zrot)
    zebra_heads.append((zp, head_p, i))

# --- lion + lionne --------------------------------------------------------
def make_lion(name, x, z, mane=True):
    p = empty(name, (x, 0, z))
    p.rotation_euler = (0, math.radians(20), 0)
    body = sphere(f"{name}_body", r=0.32, segs=14, rings=10, loc=(0, 0.55, 0), parent=p, mat=MAT_LION_BODY if mane else MAT_LIONESS)
    body.scale = (1.7, 0.9, 0.8)
    # head
    head_p = empty(f"{name}_head_p", (0.45, 0.70, 0), parent=p)
    head = sphere(f"{name}_head", r=0.20, segs=12, rings=8, loc=(0, 0, 0), parent=head_p, mat=MAT_LION_BODY if mane else MAT_LIONESS)
    head.scale = (1.2, 0.9, 0.9)
    # mane around head if male
    if mane:
        for k in range(6):
            ka = k * (math.pi * 2 / 6)
            mn = sphere(f"{name}_mane_{k}", r=0.12, segs=10, rings=8, loc=(math.cos(ka) * 0.22, math.sin(ka) * 0.10, math.sin(ka) * 0.22), parent=head_p, mat=MAT_LION_MANE)
    # ears
    for side, dz in [("L", 0.10), ("R", -0.10)]:
        ear = sphere(f"{name}_ear_{side}", r=0.05, segs=8, rings=6, loc=(-0.08, 0.18, dz), parent=head_p, mat=MAT_LION_BODY if mane else MAT_LIONESS)
    # eyes
    for side, dz in [("L", 0.08), ("R", -0.08)]:
        eye = sphere(f"{name}_eye_{side}", r=0.025, segs=8, rings=6, loc=(0.15, 0.05, dz), parent=head_p, mat=MAT_EYE_BLACK)
    # snout
    snout = sphere(f"{name}_snout", r=0.08, segs=8, rings=6, loc=(0.20, -0.05, 0), parent=head_p, mat=MAT_LION_BODY if mane else MAT_LIONESS)
    snout.scale = (1.2, 0.8, 0.9)
    # 4 legs (low, lying or standing)
    for k, (lx, lz) in enumerate([(0.30, 0.18), (0.30, -0.18), (-0.30, 0.18), (-0.30, -0.18)]):
        leg = cube(f"{name}_leg_{k}", size=1.0, loc=(lx, 0.25, lz), parent=p, mat=MAT_LION_BODY if mane else MAT_LIONESS)
        leg.scale = (0.08, 0.45, 0.08)
    # tail (animated separately)
    tail_p = empty(f"{name}_tail_p", (-0.60, 0.55, 0), parent=p)
    tail = cone(f"{name}_tail", r1=0.04, r2=0.02, depth=0.5, segs=6, loc=(-0.25, 0, 0), parent=tail_p, mat=MAT_LION_BODY if mane else MAT_LIONESS)
    tail.rotation_euler = (0, 0, math.radians(90))
    # tail tuft
    tuft = sphere(f"{name}_tuft", r=0.06, segs=8, rings=6, loc=(-0.55, 0, 0), parent=tail_p, mat=MAT_LION_MANE)
    return p, head_p, tail_p

lion_p, lion_head, lion_tail = make_lion("lion", 6, -2, mane=True)
lioness_p, lioness_head, lioness_tail = make_lion("lioness", 7, -3, mane=False)

# --- 6 oiseaux flying ----------------------------------------------------
birds = []
for i in range(6):
    a = i * (math.pi * 2 / 6) + 0.3
    r = 7.0
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 8.5 + random.uniform(-0.5, 0.5)
    bp = empty(f"bird_{i}", (bx, by, bz))
    body = sphere(f"bird_{i}_body", r=0.12, segs=10, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD)
    body.scale = (1.5, 0.6, 1.0)
    for side, xx in (("L", -0.28), ("R", 0.28)):
        w = cube(f"bird_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=bp, mat=MAT_BIRD)
        w.scale = (0.25, 0.02, 0.10)
    birds.append((bp, a, r, by))

# --- 2 rochers énormes -----------------------------------------------
for i, (rx, rz, rs) in enumerate([(10, -6, 1.6), (-10, -3, 1.4)]):
    rp = empty(f"rock_big_{i}", (rx, 0, rz))
    body = sphere(f"rock_{i}_b", r=rs, segs=16, rings=10, loc=(0, rs * 0.5, 0), parent=rp, mat=MAT_ROCK)
    body.scale = (1.2, 0.7, 1.0)

# plateau rocher (large flat)
plateau = empty("plateau", (-9, 0, -7))
pl_base = cube("plateau_base", size=1.0, loc=(0, 0.6, 0), parent=plateau, mat=MAT_ROCK)
pl_base.scale = (3.0, 0.6, 2.0)
pl_top = cube("plateau_top", size=1.0, loc=(0, 1.1, 0), parent=plateau, mat=MAT_ROCK)
pl_top.scale = (2.7, 0.1, 1.8)

# --- 3 buissons ------------------------------------------------------
for i, (bx, bz) in enumerate([(0, -6), (-6, -7), (5, -6)]):
    bp = empty(f"bush_{i}", (bx, 0, bz))
    for k in range(4):
        ka = k * (math.pi * 2 / 4)
        b = sphere(f"bush_{i}_{k}", r=0.30, segs=10, rings=8, loc=(math.cos(ka) * 0.25, 0.25, math.sin(ka) * 0.25), parent=bp, mat=MAT_BUSH)
        b.scale = (1.0, 0.7, 1.0)

# --- 8 termitières -------------------------------------------------
for i in range(8):
    tx = random.uniform(-13, 13)
    tz = random.uniform(-9, 9)
    h = random.uniform(0.6, 1.0)
    t = cone(f"termite_{i}", r1=0.30, r2=0.05, depth=h, segs=8, loc=(tx, h / 2, tz), mat=MAT_TERMITE)
    t.rotation_euler = (math.radians(90), 0, 0)

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

# 30 grass tufts sway
for gp, idx in grass_tufts:
    phase = idx * 0.3
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(8) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(gp, f, (bend, 0, bend * 0.5))

# 3 acacia canopies sway
for i, canopy in enumerate(acacia_canopies):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(3) * math.sin(tt * math.pi * 2.0 + phase)
        kf_rot(canopy, f, (bend, 0, bend * 0.5))

# 2 elephant heads bob
for i, head_p in enumerate(elephant_heads):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bob = math.radians(6) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(head_p, f, (bob, 0, 0))

# 3 giraffes : neck swing + head bob
for i, (gp, head_p, neck_p) in enumerate(giraffe_objs):
    phase = i * 0.5
    base_rot = neck_p.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        neck_swing = math.radians(5) * math.sin(tt * math.pi * 2.0 + phase)
        kf_rot(neck_p, f, (neck_swing, 0, 0))
        head_bob = math.radians(8) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(head_p, f, (head_bob, 0, 0))

# 4 zebras head bob (grazing)
for zp, head_p, idx in zebra_heads:
    phase = idx * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bob = math.radians(10) * math.sin(tt * math.pi * 5.0 + phase)
        kf_rot(head_p, f, (bob, 0, 0))

# lion tail swish
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    swish = math.radians(20) * math.sin(tt * math.pi * 4.0)
    kf_rot(lion_tail, f, (0, 0, swish))
    kf_rot(lioness_tail, f, (0, 0, math.radians(15) * math.sin(tt * math.pi * 3.0 + 0.5)))

# 6 birds orbit
for bp, a0, r, by in birds:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r
        bz = math.sin(angle) * r
        by_a = by + 0.3 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(15) * math.sin(tt * math.pi * 8.0)))

# sun + halo pulse
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s_halo = 1.0 + 0.12 * math.sin(tt * math.pi * 3.0)
    kf_scale(sun_halo, f, (s_halo, s_halo, s_halo))
    s_sun = 1.0 + 0.05 * math.sin(tt * math.pi * 5.0)
    kf_scale(sun, f, (s_sun, s_sun, s_sun))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_savanna] wrote {OUT}")
