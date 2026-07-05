"""
proc_volcano.py — 110e procédural AuroraIA, Phase F++++.

Volcan en éruption : cône volcanique + cratère + 3 coulées de lave qui
descendent les flancs + colonne de fumée + 30 particules de lave éjectée
+ rocher au pied + arbres carbonisés autour + sol craquelé brûlant.

Animation :
- 30 particules lave : éruption (arc parabolique), scale pulse, fade
- colonne de fumée : scale + rotation lent
- lueur cratère : émission pulse
- coulées de lave : émission pulse différentiel

Sortie : output/3d/pbr_volcano_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_volcano_proc.glb"))

random.seed(0xCAFEE)

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
MAT_GROUND = make_mat("ground", (0.18, 0.13, 0.10), roughness=0.95)
MAT_GROUND_HOT = make_mat(
    "ground_hot", (0.45, 0.12, 0.05), roughness=0.7,
    emi=(0.8, 0.2, 0.05), emi_strength=0.4,
)
MAT_ROCK = make_mat("rock_dark", (0.12, 0.10, 0.09), roughness=0.95)
MAT_VOLCANO_BASE = make_mat("volcano_dark", (0.10, 0.08, 0.07), roughness=0.9)
MAT_VOLCANO_TOP = make_mat("volcano_ash", (0.20, 0.16, 0.13), roughness=0.85)
MAT_LAVA = make_mat(
    "lava", (1.0, 0.4, 0.05), roughness=0.3,
    emi=(1.0, 0.4, 0.05), emi_strength=4.5,
)
MAT_LAVA_HOT = make_mat(
    "lava_hot", (1.0, 0.85, 0.2), roughness=0.2,
    emi=(1.0, 0.85, 0.2), emi_strength=7.0,
)
MAT_LAVA_PARTICLE = make_mat(
    "lava_particle", (1.0, 0.55, 0.1), roughness=0.2,
    emi=(1.0, 0.55, 0.1), emi_strength=6.0,
)
MAT_SMOKE = make_mat(
    "smoke", (0.3, 0.28, 0.26), roughness=1.0, alpha=0.65,
    emi=(0.4, 0.2, 0.1), emi_strength=0.3,
)
MAT_TREE_BURNT = make_mat("tree_burnt", (0.08, 0.06, 0.05), roughness=0.95)
MAT_SKY = make_mat("sky_red", (0.25, 0.10, 0.08), roughness=1.0,
                    emi=(0.5, 0.15, 0.08), emi_strength=0.4)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 12, 4), mat=MAT_SKY)
sky.scale = (16, 0.1, 10)

ground = cube("ground", size=1.0, loc=(0, 0, -0.05), mat=MAT_GROUND)
ground.scale = (20, 0.1, 20)

# hot cracked ground around volcano base
hot_ground = cube("ground_hot", size=1.0, loc=(0, 0.01, 0), mat=MAT_GROUND_HOT)
hot_ground.scale = (8, 0.1, 8)

# --- volcano cone -----------------------------------------------------------
# 2-layer cone : wide dark base + narrower ashen top with crater
base = cone("volcano_base", r1=4.5, r2=2.2, depth=2.8, segs=24, loc=(0, 1.4, 0), mat=MAT_VOLCANO_BASE)
base.rotation_euler = (math.radians(90), 0, 0)

top = cone("volcano_top", r1=2.2, r2=1.4, depth=1.2, segs=20, loc=(0, 3.4, 0), mat=MAT_VOLCANO_TOP)
top.rotation_euler = (math.radians(90), 0, 0)

# crater rim (small ring at top)
crater_rim = cone("crater_rim", r1=1.4, r2=1.5, depth=0.15, segs=20, loc=(0, 4.05, 0), mat=MAT_VOLCANO_TOP)
crater_rim.rotation_euler = (math.radians(90), 0, 0)

# crater lava pool (hot glowing disc inside crater)
crater_pool = cone("crater_pool", r1=1.2, r2=1.2, depth=0.1, segs=20, loc=(0, 4.05, 0), mat=MAT_LAVA_HOT)
crater_pool.rotation_euler = (math.radians(90), 0, 0)

# crater bulge (sphere of lava bubbling up)
crater_bulge = sphere("crater_bulge", r=0.8, segs=20, rings=14, loc=(0, 4.2, 0), mat=MAT_LAVA_HOT)
crater_bulge.scale = (1.0, 0.5, 1.0)

# --- 3 lava flows running down the sides ------------------------------------
# Each flow is a chain of stretched spheres trailing from crater rim down
def make_lava_flow(name, angle, segments=8):
    parent = empty(f"flow_{name}", (0, 0, 0))
    for i in range(segments):
        t = i / (segments - 1)
        # start at crater rim, descend
        r = 1.4 + t * 3.0
        y = 4.0 - t * 3.8
        x = math.cos(angle) * r
        z = math.sin(angle) * r
        # alternate hot/normal
        m = MAT_LAVA_HOT if i < 3 else MAT_LAVA
        seg = sphere(f"flow_{name}_{i}", r=0.32 - 0.02 * i, segs=14, rings=10, loc=(x, y, z), parent=parent, mat=m)
        # squash vertical to look like flow
        seg.scale = (1.2, 0.5, 1.2)
    return parent

flow_a = make_lava_flow("a", math.radians(0))
flow_b = make_lava_flow("b", math.radians(130))
flow_c = make_lava_flow("c", math.radians(230))

# --- smoke plume ------------------------------------------------------------
smoke_pivot = empty("smoke_pivot", (0, 4.2, 0))
# 5 stacked smoke puffs at increasing scale
for i in range(5):
    y = 0.8 + i * 1.0
    r = 0.7 + i * 0.35
    puff = sphere(f"smoke_{i}", r=r, segs=18, rings=14, loc=(0, y, 0), parent=smoke_pivot, mat=MAT_SMOKE)
    puff.scale = (1.0, 0.85, 1.0)

# --- 30 lava ejection particles ---------------------------------------------
particles = []
for i in range(30):
    angle = random.uniform(0, math.pi * 2)
    speed = random.uniform(0.7, 1.4)
    p = sphere(
        f"lava_p_{i}", r=random.uniform(0.06, 0.12), segs=8, rings=6,
        loc=(0, 4.2, 0), mat=MAT_LAVA_PARTICLE,
    )
    particles.append((p, angle, speed, i))

# --- 6 burnt trees around base ---------------------------------------------
for i in range(6):
    a = i * (math.pi * 2 / 6) + 0.3
    tx = math.cos(a) * 6.0
    tz = math.sin(a) * 6.0
    trunk = cone(f"trunk_{i}", r1=0.18, r2=0.12, depth=1.3, segs=10, loc=(tx, 0.65, tz), mat=MAT_TREE_BURNT)
    trunk.rotation_euler = (math.radians(90), 0, 0)
    # 3 burnt branches
    for b in range(3):
        ba = b * (math.pi * 2 / 3)
        br = cone(f"branch_{i}_{b}", r1=0.05, r2=0.02, depth=0.6, segs=6, loc=(tx + math.cos(ba) * 0.25, 1.1, tz + math.sin(ba) * 0.25), mat=MAT_TREE_BURNT)
        br.rotation_euler = (math.radians(60), 0, ba)

# --- 4 rocks scattered ------------------------------------------------------
for i in range(4):
    a = i * (math.pi * 2 / 4) + 0.6
    rx = math.cos(a) * 7.5
    rz = math.sin(a) * 7.5
    rock = sphere(f"rock_{i}", r=random.uniform(0.35, 0.55), segs=14, rings=10, loc=(rx, 0.3, rz), mat=MAT_ROCK)
    rock.scale = (1.1, 0.7, 0.95)

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

# crater bulge pulse
for f in range(1, FRAMES + 1, 3):
    t = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.25 * math.sin(t * math.pi * 6.0)
    kf_scale(crater_bulge, f, (s, 0.5 * s, s))

# crater pool subtle wobble
for f in range(1, FRAMES + 1, 4):
    t = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.05 * math.sin(t * math.pi * 4.0)
    kf_scale(crater_pool, f, (s, 1.0, s))

# smoke plume slow rise + rotate
for f in range(1, FRAMES + 1, 3):
    t = (f - 1) / (FRAMES - 1)
    kf_rot(smoke_pivot, f, (0, t * math.pi * 0.6, 0))
    s = 1.0 + 0.12 * math.sin(t * math.pi * 4.0)
    kf_scale(smoke_pivot, f, (s, 1.0 + 0.05 * t, s))

# particles : parabolic eruption — start at crater, rise + fall
for p, angle, speed, idx in particles:
    phase = (idx * 6) % 60
    for f in range(1, FRAMES + 1, 2):
        local_f = (f + phase) % 60
        lt = local_f / 60.0
        # parabolic : y rises then falls
        y = 4.2 + speed * 3.0 * lt - 0.5 * 9.0 * (lt ** 2) * 0.6
        if y < 0.2:
            y = 0.2
        radial = speed * 1.5 * lt
        x = math.cos(angle) * radial
        z = math.sin(angle) * radial
        kf_loc(p, f, (x, y, z))
        # scale fade : start big, shrink near end
        s = 1.0 - 0.6 * lt
        if s < 0.2:
            s = 0.2
        kf_scale(p, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_volcano] wrote {OUT}")
