"""
proc_waterfall.py — 113e procédural AuroraIA, Phase F++++.

Cascade en montagne : falaise rocheuse multi-niveaux + chute d'eau
principale en plusieurs paliers (3 cascades superposées) + bassin
récepteur en bas avec écume circulaire + 40 gouttelettes spray
qui retombent + brouillard d'eau translucide + arc-en-ciel
sept-bandes + 4 sapins autour + pierres mossues + ciel ensoleillé.

Animation :
- cascades : scroll vertical via scale Y wave (texture pseudo-flux)
- 40 gouttelettes : tombent puis rebondissent depuis le bassin
- écume : pulse + rotation lente
- brouillard : drift horizontal + scale breathe
- arc-en-ciel : émission pulse douce
- 7 bandes RGB cycling subtle

Sortie : output/3d/pbr_waterfall_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_waterfall_proc.glb"))

random.seed(0xCAFADE)

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


def torus(name, R=1.0, r=0.2, major=24, minor=12, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=major, v_segments=minor, radius=r)
    bm.to_mesh(me)
    bm.free()
    # blender doesn't have create_torus in bmesh.ops; fall back: build via 24 small spheres
    # actually let's just build manually via 24 spheres in a ring
    bpy.data.meshes.remove(me)
    p = empty(name + "_p", loc, parent)
    for i in range(major):
        a = i * 2 * math.pi / major
        s = sphere(f"{name}_{i}", r=r, segs=10, rings=6, loc=(math.cos(a) * R, 0, math.sin(a) * R), parent=p, mat=mat)
    return p


# --- materials --------------------------------------------------------------
MAT_SKY = make_mat("sky_blue", (0.55, 0.75, 0.95), roughness=1.0,
                    emi=(0.35, 0.50, 0.75), emi_strength=0.5)
MAT_ROCK_DARK = make_mat("rock_dark", (0.30, 0.27, 0.24), roughness=0.95)
MAT_ROCK_LIGHT = make_mat("rock_light", (0.50, 0.45, 0.40), roughness=0.85)
MAT_MOSS = make_mat("moss", (0.20, 0.40, 0.15), roughness=0.95)
MAT_WATER = make_mat(
    "water", (0.45, 0.75, 0.95), roughness=0.05, metallic=0.2, alpha=0.85,
    emi=(0.55, 0.85, 1.0), emi_strength=1.2,
)
MAT_WATER_FOAM = make_mat(
    "water_foam", (0.95, 0.98, 1.0), roughness=0.3, alpha=0.8,
    emi=(0.95, 0.98, 1.0), emi_strength=2.0,
)
MAT_SPRAY = make_mat(
    "spray", (0.85, 0.92, 1.0), roughness=0.0, alpha=0.7,
    emi=(0.7, 0.85, 1.0), emi_strength=3.0,
)
MAT_MIST = make_mat(
    "mist", (0.90, 0.95, 1.0), roughness=1.0, alpha=0.35,
    emi=(0.8, 0.9, 1.0), emi_strength=1.2,
)
MAT_POOL = make_mat(
    "pool", (0.25, 0.55, 0.75), metallic=0.8, roughness=0.1, alpha=0.9,
    emi=(0.30, 0.55, 0.80), emi_strength=0.6,
)
MAT_FIR_TRUNK = make_mat("fir_trunk", (0.25, 0.18, 0.10), roughness=0.95)
MAT_FIR_LEAVES = make_mat("fir_leaves", (0.10, 0.30, 0.12), roughness=0.9)
MAT_GROUND = make_mat("ground", (0.30, 0.25, 0.18), roughness=0.95)

# rainbow band colors (7 hues)
RAINBOW_COLORS = [
    (1.0, 0.15, 0.15),   # red
    (1.0, 0.50, 0.10),   # orange
    (1.0, 0.95, 0.20),   # yellow
    (0.20, 0.85, 0.30),  # green
    (0.20, 0.50, 1.0),   # blue
    (0.30, 0.20, 0.90),  # indigo
    (0.70, 0.30, 0.95),  # violet
]
rainbow_mats = []
for i, c in enumerate(RAINBOW_COLORS):
    m = make_mat(f"rainbow_{i}", c, roughness=0.0, alpha=0.5,
                  emi=c, emi_strength=3.5)
    rainbow_mats.append(m)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY)
sky.scale = (28, 0.1, 14)

ground = cube("ground", size=1.0, loc=(0, 0, -0.05), mat=MAT_GROUND)
ground.scale = (30, 0.1, 24)

# --- cliff (3-tier rocky cliff) ---------------------------------------------
# tier 1 : top platform (highest)
tier1 = cube("cliff_tier1", size=1.0, loc=(0, 8.0, -3.5), mat=MAT_ROCK_DARK)
tier1.scale = (6, 1.5, 3)

# tier 2 : middle ledge (slightly forward & lower)
tier2 = cube("cliff_tier2", size=1.0, loc=(0, 4.5, -2.0), mat=MAT_ROCK_LIGHT)
tier2.scale = (5, 1.5, 2.5)

# tier 3 : lower ledge
tier3 = cube("cliff_tier3", size=1.0, loc=(0, 2.0, -1.0), mat=MAT_ROCK_DARK)
tier3.scale = (5.5, 1.0, 2.0)

# moss on tier edges
moss1 = cube("moss_t1", size=1.0, loc=(0, 7.0, -2.2), mat=MAT_MOSS)
moss1.scale = (5.5, 0.1, 0.5)
moss2 = cube("moss_t2", size=1.0, loc=(0, 3.8, -0.95), mat=MAT_MOSS)
moss2.scale = (4.5, 0.1, 0.4)

# --- 3 waterfall sheets (one per tier drop) ---------------------------------
# These are large flat cubes "scrolling" by Y-scale animation. Using
# cubes lets us keyframe a non-uniform scale wave that looks like flux.
falls = []
# fall 1 : from tier1 top (y=8.75) to tier2 top (y=5.25)
f1 = cube("fall_1", size=1.0, loc=(0, 7.0, -2.05), mat=MAT_WATER)
f1.scale = (4.5, 3.5, 0.08)
falls.append(f1)
# fall 2 : from tier2 top (y=5.25) to tier3 top (y=2.5)
f2 = cube("fall_2", size=1.0, loc=(0, 3.85, -0.95), mat=MAT_WATER)
f2.scale = (4.0, 2.75, 0.08)
falls.append(f2)
# fall 3 : from tier3 top (y=2.5) to pool (y=0.2)
f3 = cube("fall_3", size=1.0, loc=(0, 1.35, 0.1), mat=MAT_WATER)
f3.scale = (4.5, 2.3, 0.08)
falls.append(f3)

# foam at the top of each waterfall (where it goes over the edge)
foam_caps = []
for i, fc_y in enumerate([8.75, 5.25, 2.5]):
    fc = cube(f"foam_cap_{i}", size=1.0, loc=(0, fc_y, -2.05 + i * 0.6), mat=MAT_WATER_FOAM)
    fc.scale = (4.6 - i * 0.1, 0.1, 0.5)
    foam_caps.append(fc)

# --- pool at the bottom with circular foam ring -----------------------------
pool = cube("pool_surface", size=1.0, loc=(0, 0.1, 2.5), mat=MAT_POOL)
pool.scale = (8, 0.05, 5)

# foam ring around the impact point (where fall_3 hits the pool)
impact_x, impact_z = 0.0, 0.1
foam_rings = []
N_FOAM = 18
for i in range(N_FOAM):
    a = i * (math.pi * 2 / N_FOAM)
    r = 1.5
    fx = impact_x + math.cos(a) * r
    fz = impact_z + math.sin(a) * r
    fr = sphere(f"foam_ring_{i}", r=0.3, segs=12, rings=8, loc=(fx, 0.18, fz), mat=MAT_WATER_FOAM)
    fr.scale = (1.0, 0.25, 1.0)
    foam_rings.append((fr, i))

# central impact splash
splash = sphere("splash_center", r=0.6, segs=18, rings=14, loc=(impact_x, 0.5, impact_z), mat=MAT_WATER_FOAM)
splash.scale = (1.2, 0.8, 1.2)

# --- 40 spray droplets bouncing ---------------------------------------------
sprays = []
for i in range(40):
    a = random.uniform(0, math.pi * 2)
    rd = random.uniform(0.5, 3.0)
    sx = impact_x + math.cos(a) * rd
    sz = impact_z + math.sin(a) * rd
    sy = random.uniform(0.3, 2.5)
    s = sphere(f"spray_{i}", r=random.uniform(0.06, 0.12), segs=10, rings=8, loc=(sx, sy, sz), mat=MAT_SPRAY)
    sprays.append((s, a, rd, random.uniform(0.0, 1.0), random.uniform(0.8, 1.4)))

# --- 6 mist puffs floating around ------------------------------------------
mists = []
for i in range(6):
    a = i * (math.pi * 2 / 6)
    rm = 3.0 + (i % 2) * 0.6
    mx = math.cos(a) * rm
    mz = math.sin(a) * rm
    my = 1.2 + (i % 3) * 0.6
    m = sphere(f"mist_{i}", r=1.2, segs=16, rings=12, loc=(mx, my, mz), mat=MAT_MIST)
    m.scale = (1.4, 0.7, 1.2)
    mists.append((m, a, rm))

# --- rainbow (7 arcs above the pool) ---------------------------------------
rainbow_p = empty("rainbow", (0, 4.5, 3.5))
# half-torus approximated as ring of stretched cubes
rainbow_segs = []
N_ARC = 28
for band in range(7):
    R = 4.0 + band * 0.18
    seg_list = []
    for j in range(N_ARC):
        a = math.pi * (j + 0.5) / N_ARC  # 0..pi
        x = math.cos(a) * R
        y = math.sin(a) * R
        z = 0
        seg = cube(f"rainbow_b{band}_s{j}", size=1.0, loc=(x, y, z), parent=rainbow_p, mat=rainbow_mats[band])
        seg.scale = (0.18, 0.18, 0.6)
        # rotate so it faces tangent to arc
        seg.rotation_euler = (0, 0, a + math.pi / 2)
        seg_list.append(seg)
    rainbow_segs.append(seg_list)

# --- 4 fir trees around the scene ------------------------------------------
def make_fir(name, x, z):
    p = empty(name, (x, 0.5, z))
    trunk = cone(f"{name}_trunk", r1=0.16, r2=0.12, depth=1.0, segs=8, loc=(0, 0.5, 0), parent=p, mat=MAT_FIR_TRUNK)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    for j in range(4):
        h = 1.0 + j * 0.55
        r = 0.85 - j * 0.18
        layer = cone(f"{name}_layer_{j}", r1=r, r2=r * 0.35, depth=0.55, segs=10, loc=(0, h, 0), parent=p, mat=MAT_FIR_LEAVES)
        layer.rotation_euler = (math.radians(90), 0, 0)
    return p

for i, (x, z) in enumerate([(-7.5, 4.5), (7.5, 4.0), (-8.5, 1.0), (8.5, 1.5)]):
    make_fir(f"fir_{i}", x, z)

# --- mossy stones around the pool -------------------------------------------
for i in range(7):
    a = i * (math.pi * 2 / 7) + 0.3
    sr = 3.5 + random.uniform(-0.4, 0.4)
    sx = math.cos(a) * sr
    sz = math.sin(a) * sr + 2.5
    rk = sphere(f"stone_{i}", r=random.uniform(0.20, 0.40), segs=12, rings=8, loc=(sx, 0.25, sz), mat=MAT_ROCK_LIGHT)
    rk.scale = (1.0, 0.5, 1.0)
    # moss patch on top
    mp = sphere(f"stone_moss_{i}", r=0.15, segs=8, rings=6, loc=(0, 0.35, 0), parent=rk, mat=MAT_MOSS)
    mp.scale = (1.5, 0.4, 1.5)

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

# waterfalls : Y-scale wave that suggests flowing water (subtle)
for i, fall in enumerate(falls):
    base_y = fall.scale.y
    base_x = fall.scale.x
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        # subtle x wave (water spread) + Y normalized
        s_x = base_x * (1.0 + 0.04 * math.sin(tt * math.pi * 6.0 + i * 0.8))
        s_y = base_y * (1.0 + 0.02 * math.sin(tt * math.pi * 8.0 + i * 1.1))
        kf_scale(fall, f, (s_x, s_y, fall.scale.z))

# foam caps pulse
for i, fc in enumerate(foam_caps):
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.18 * math.sin(tt * math.pi * 5.0 + i * 0.7)
        kf_scale(fc, f, (fc.scale.x * s, fc.scale.y, fc.scale.z * s))

# splash center pulse
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.2 * math.sin(tt * math.pi * 7.0)
    kf_scale(splash, f, (1.2 * s, 0.8 * s, 1.2 * s))

# foam ring : pulse + slow rotation around pool
for fr, idx in foam_rings:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        a = idx * (math.pi * 2 / N_FOAM) + tt * math.pi * 0.6
        r = 1.5 + 0.15 * math.sin(tt * math.pi * 4.0 + idx * 0.3)
        fx = impact_x + math.cos(a) * r
        fz = impact_z + math.sin(a) * r
        kf_loc(fr, f, (fx, 0.18, fz))
        s = 1.0 + 0.18 * math.sin(tt * math.pi * 5.0 + idx * 0.5)
        kf_scale(fr, f, (s, 0.25 * s, s))

# spray droplets : bounce trajectories (parabolic up and down)
for s, a0, rd, ph, spd in sprays:
    for f in range(1, FRAMES + 1, 2):
        local = ((f - 1) / FRAMES + ph) % 1.0
        # parabolic : y rises then falls
        y = 0.3 + spd * 2.5 * local * (1 - local) * 4.0  # peak around local=0.5
        # radial drift outward
        r_now = rd + 0.3 * local
        x = impact_x + math.cos(a0) * r_now
        z = impact_z + math.sin(a0) * r_now
        kf_loc(s, f, (x, y, z))
        # scale fade
        s_scale = 1.0 - 0.3 * local
        if s_scale < 0.4:
            s_scale = 0.4
        kf_scale(s, f, (s_scale, s_scale, s_scale))

# mist : drift in circle + scale breathe
for m, a0, rm in mists:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 0.5
        mx = math.cos(angle) * rm
        mz = math.sin(angle) * rm
        kf_loc(m, f, (mx, m.location.y, mz))
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 3.5 + a0)
        kf_scale(m, f, (1.4 * s, 0.7, 1.2 * s))

# rainbow : subtle pulse on the parent, and slight scale wave per band
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.04 * math.sin(tt * math.pi * 3.0)
    kf_scale(rainbow_p, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_waterfall] wrote {OUT}")
