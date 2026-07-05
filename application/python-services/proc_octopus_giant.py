"""
proc_octopus_giant.py — 152e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Pieuvre géante sous-marine :
- corps bulbous bevelé (sphère étirée smooth)
- 8 tentacules avec ventouses (chacun 8 segments propagated wave indépendant)
- 2 grands yeux émissifs jaunes pupilles noires
- bec dur central
- 5 coraux + 3 poissons + algues
- 30 bulles + 4 cailloux
- ciel sous-marin bleu profond

Animations multi-axes simultanées :
- 8 tentacules : wave indépendant chacun (fréquence/phase propre)
- eyes pulse intense
- body pulse breathing
- 30 bulles montent

Sortie : output/3d/pbr_octopus_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_octopus_proc.glb"))

random.seed(0xCAFF22)

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
MAT_WATER_BG = make_mat("water_bg", (0.05, 0.20, 0.35), roughness=1.0, emi=(0.10, 0.25, 0.40), emi_strength=0.5)
MAT_WATER_TOP = make_mat("water_top", (0.20, 0.55, 0.70), metallic=0.5, roughness=0.1, alpha=0.6, emi=(0.20, 0.55, 0.70), emi_strength=0.6)
MAT_SAND = make_mat("sand", (0.85, 0.75, 0.50), roughness=0.95)
MAT_OCTOPUS_BODY = make_mat("octo_body", (0.65, 0.15, 0.45), metallic=0.20, roughness=0.40, emi=(0.20, 0.05, 0.15), emi_strength=0.25)
MAT_OCTOPUS_LIGHT = make_mat("octo_light", (0.85, 0.30, 0.65), metallic=0.20, roughness=0.40, emi=(0.30, 0.10, 0.20), emi_strength=0.30)
MAT_OCTOPUS_DARK = make_mat("octo_dark", (0.30, 0.05, 0.20), roughness=0.5)
MAT_SUCKER = make_mat("sucker", (0.95, 0.55, 0.55), roughness=0.5, emi=(0.30, 0.15, 0.15), emi_strength=0.3)
MAT_EYE_YELLOW = make_mat("eye_yellow", (1.0, 0.90, 0.20), roughness=0.0, emi=(1.0, 0.90, 0.20), emi_strength=12.0)
MAT_PUPIL_BLACK = make_mat("pupil", (0.02, 0.02, 0.02), roughness=0.0)
MAT_BEAK = make_mat("beak", (0.20, 0.15, 0.10), metallic=0.5, roughness=0.4)
MAT_CORAL_PINK = make_mat("coral_pink", (1.0, 0.45, 0.65), roughness=0.5, emi=(0.40, 0.15, 0.25), emi_strength=0.5)
MAT_CORAL_ORANGE = make_mat("coral_orange", (1.0, 0.55, 0.20), roughness=0.5, emi=(0.50, 0.25, 0.08), emi_strength=0.5)
MAT_CORAL_PURPLE = make_mat("coral_purple", (0.65, 0.25, 0.95), roughness=0.5, emi=(0.30, 0.10, 0.45), emi_strength=0.5)
MAT_FISH_R = make_mat("fish_r", (1.0, 0.45, 0.10), roughness=0.5, emi=(0.50, 0.20, 0.05), emi_strength=0.4)
MAT_FISH_B = make_mat("fish_b", (0.20, 0.50, 1.0), roughness=0.5, emi=(0.10, 0.20, 0.50), emi_strength=0.4)
MAT_FISH_Y = make_mat("fish_y", (1.0, 0.90, 0.20), roughness=0.5, emi=(0.40, 0.35, 0.05), emi_strength=0.4)
MAT_ALGAE = make_mat("algae", (0.10, 0.55, 0.20), roughness=0.85, emi=(0.05, 0.25, 0.10), emi_strength=0.3)
MAT_BUBBLE = make_mat("bubble", (0.85, 0.95, 1.0), roughness=0.0, alpha=0.45, emi=(0.80, 0.92, 1.0), emi_strength=1.5)
MAT_ROCK = make_mat("rock", (0.25, 0.25, 0.28), roughness=0.95)
MAT_RAY = make_mat("ray", (1.0, 0.95, 0.65), roughness=0.0, alpha=0.20, emi=(1.0, 0.95, 0.65), emi_strength=2.0)

# --- backdrop : deep water -----------------------------------
back = beveled_cube("water_bg", (40, 0.2, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 6), mat=MAT_WATER_BG)
top = beveled_cube("water_top", (40, 0.1, 6), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 0), mat=MAT_WATER_TOP)

# 4 light rays from above (alpha translucent)
for i in range(4):
    rx = -8 + i * 4 + random.uniform(-1, 1)
    rp = empty(f"ray_p_{i}", (rx, 6, 0))
    rp.rotation_euler = (0, 0, math.radians(random.uniform(-5, 5)))
    ray = beveled_cube(f"ray_{i}", (0.8, 12.0, 0.8), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=rp, mat=MAT_RAY)

# --- sand floor -----------------------------------------
sand = beveled_cube("sand", (30, 0.1, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_SAND)

# 4 rocks
for i in range(4):
    rx = random.uniform(-10, 10)
    rz = random.uniform(-7, 7)
    if abs(rx) < 3 and abs(rz) < 3:
        continue
    rock = smooth_sphere(f"rock_{i}", r=random.uniform(0.35, 0.65), segs=18, rings=12, loc=(rx, 0.20, rz), mat=MAT_ROCK, scale=(1.3, 0.6, 1.0))

# 5 coraux
coral_data = [
    (-4, -2, MAT_CORAL_PINK, "branching"),
    (4, -2, MAT_CORAL_ORANGE, "fan"),
    (-6, 2, MAT_CORAL_PURPLE, "branching"),
    (6, 2, MAT_CORAL_PINK, "fan"),
    (0, 5, MAT_CORAL_ORANGE, "branching"),
]
for i, (cx, cz, mat, kind) in enumerate(coral_data):
    cp = empty(f"coral_{i}", (cx, 0, cz))
    if kind == "branching":
        # base + 5 branches with 3 spheres each
        base = smooth_sphere(f"coral_{i}_base", r=0.20, segs=14, rings=10, loc=(0, 0.10, 0), parent=cp, mat=mat)
        for k in range(5):
            a = k * (math.pi * 2 / 5)
            bx = math.cos(a) * 0.12
            bz = math.sin(a) * 0.12
            for j in range(3):
                ys = 0.25 + j * 0.20
                rj = 0.10 - j * 0.02
                seg = smooth_sphere(f"coral_{i}_b{k}_{j}", r=rj, segs=12, rings=8, loc=(bx * (1 + j * 0.4), ys, bz * (1 + j * 0.4)), parent=cp, mat=mat)
    else:  # fan
        base = smooth_sphere(f"coral_{i}_base", r=0.18, segs=14, rings=10, loc=(0, 0.10, 0), parent=cp, mat=mat)
        # 9 fan segments
        for j in range(9):
            a = -math.pi / 3 + j * (2 * math.pi / 3 / 8)
            sx = 0.10 * math.cos(a)
            sy = 0.30 + 0.50 * math.sin(a)
            sz = 0
            blade = beveled_cube(f"coral_{i}_blade_{j}", (0.04, 0.50, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(sx, sy, sz), parent=cp, mat=mat)
            blade.rotation_euler = (0, 0, a)

# 4 algae filaments sway
algae_objs = []
for i, (ax, az) in enumerate([(-3, 5), (3, 5), (-5, 0), (5, 0)]):
    ap = empty(f"algae_{i}", (ax, 0, az))
    for j in range(5):
        h = 0.30 + j * 0.45
        seg = smooth_cone(f"algae_{i}_seg_{j}", r1=0.06 - j * 0.008, r2=0.05 - j * 0.008, depth=0.45, segs=8, loc=(0, h, 0), parent=ap, mat=MAT_ALGAE)
        seg.rotation_euler = (math.radians(90), 0, 0)
    algae_objs.append(ap)

# --- OCTOPUS GIANT --------------------------------------------
octopus = empty("octopus", (0, 3.5, 0))

# body (sphère étirée bulbous)
def make_body(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=1.0)
    bmesh.ops.scale(bm, vec=(1.2, 1.5, 1.2), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0, 0)
    me.materials.append(MAT_OCTOPUS_BODY)
    smooth_shade(me)
    return o

body = make_body("octo_body_main", octopus)

# body crown / mantle (lighter top)
mantle = smooth_sphere("mantle", r=0.85, segs=28, rings=20, loc=(0, 0.65, 0), parent=octopus, mat=MAT_OCTOPUS_LIGHT, scale=(1.2, 0.85, 1.2))

# 2 large bumps on top (eye ridges)
for side, dz in [("L", 0.45), ("R", -0.45)]:
    ridge = smooth_sphere(f"eye_ridge_{side}", r=0.40, segs=20, rings=14, loc=(0.30, 0.45, dz), parent=octopus, mat=MAT_OCTOPUS_LIGHT, scale=(1.1, 0.8, 1.0))

# 2 eyes (yellow with black pupils)
eyes = []
for side, dz in [("L", 0.50), ("R", -0.50)]:
    eye = smooth_sphere(f"eye_{side}", r=0.22, segs=20, rings=14, loc=(0.50, 0.50, dz), parent=octopus, mat=MAT_EYE_YELLOW)
    eyes.append(eye)
    pupil = smooth_sphere(f"pupil_{side}", r=0.10, segs=16, rings=12, loc=(0.65, 0.50, dz), parent=octopus, mat=MAT_PUPIL_BLACK)
    pupil.scale = (0.8, 1.5, 0.5)

# beak (between tentacles, dark)
beak = smooth_cone("beak", r1=0.10, r2=0.0, depth=0.15, segs=10, loc=(0, -0.85, 0), parent=octopus, mat=MAT_BEAK)
beak.rotation_euler = (math.radians(180), 0, 0)

# --- 8 TENTACULES avec 8 segments propagated wave indépendant ---
tentacles_segments_all = []
for tk in range(8):
    base_a = tk * (math.pi * 2 / 8)
    bx0 = math.cos(base_a) * 0.6
    bz0 = math.sin(base_a) * 0.6
    tent_root = empty(f"tent_root_{tk}", (bx0, -0.6, bz0), parent=octopus)
    tent_root.rotation_euler = (0, base_a, 0)

    tentacle_segs = []
    current_parent = tent_root
    for j in range(8):
        seg_p = empty(f"tent_p_{tk}_{j}", (0.30, -0.05 * j, 0), parent=current_parent)
        # tentacle segment (sphere stretched, tapering)
        rj = 0.20 - j * 0.018
        seg = smooth_sphere(f"tent_seg_{tk}_{j}", r=rj, segs=16, rings=12, loc=(0.15, 0, 0), parent=seg_p, mat=MAT_OCTOPUS_BODY, scale=(1.4, 0.9, 0.9))
        # 2 suckers per segment (round white dots underneath)
        for s in range(2):
            sa = (s * math.pi)
            sucker = smooth_sphere(f"sucker_{tk}_{j}_{s}", r=0.035, segs=10, rings=8, loc=(0.15 + s * 0.10, -rj * 0.7, 0), parent=seg_p, mat=MAT_SUCKER, scale=(1.0, 0.4, 1.0))
        tentacle_segs.append(seg_p)
        current_parent = seg_p
    # tip
    tip = smooth_cone(f"tent_tip_{tk}", r1=rj * 0.5, r2=0.0, depth=0.15, segs=8, loc=(0.15, 0, 0), parent=current_parent, mat=MAT_OCTOPUS_DARK)
    tip.rotation_euler = (0, 0, math.radians(90))
    tentacles_segments_all.append((tent_root, tentacle_segs))

# --- 3 fish ----------------------------------------------
fishes = []
fish_data = [
    (-6, 5, 3, MAT_FISH_R, 0.30),
    (5, 6, -2, MAT_FISH_B, 0.25),
    (-3, 4, -5, MAT_FISH_Y, 0.35),
]
for i, (fx, fy, fz, mat, sc) in enumerate(fish_data):
    fp = empty(f"fish_{i}", (fx, fy, fz))
    body = smooth_sphere(f"fish_{i}_body", r=0.20 * sc, segs=18, rings=14, loc=(0, 0, 0), parent=fp, mat=mat, scale=(1.8, 0.7, 1.0))
    # tail
    tail = smooth_cone(f"fish_{i}_tail", r1=0.15 * sc, r2=0.02, depth=0.20 * sc, segs=6, loc=(-0.30 * sc, 0, 0), parent=fp, mat=mat)
    tail.rotation_euler = (0, math.radians(-90), 0)
    tail.scale = (1.0, 1.5, 0.3)
    # eye
    eye = smooth_sphere(f"fish_{i}_eye", r=0.025, segs=8, rings=6, loc=(0.15 * sc, 0.05, 0.06 * sc), parent=fp, mat=MAT_PUPIL_BLACK)
    fishes.append((fp, fx, fy, fz, i))

# --- 30 bubbles montent ----------------------------------------
bubbles = []
for i in range(30):
    bx = random.uniform(-9, 9)
    bz = random.uniform(-7, 7)
    by = random.uniform(1, 12)
    bp = smooth_sphere(f"bubble_{i}", r=random.uniform(0.06, 0.12), segs=12, rings=10, loc=(bx, by, bz), mat=MAT_BUBBLE)
    bubbles.append((bp, bx, bz, random.uniform(0, 1)))

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

# Octopus subtle drift + bob
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    bx = 0.4 * math.sin(tt * math.pi * 1.5)
    by = 3.5 + 0.30 * math.sin(tt * math.pi * 3.0)
    bz = 0.3 * math.cos(tt * math.pi * 1.2)
    kf_loc(octopus, f, (bx, by, bz))
    rotY = math.radians(15) * math.sin(tt * math.pi * 2.0)
    kf_rot(octopus, f, (0, rotY, 0))

# Body breathing pulse
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.05 * math.sin(tt * math.pi * 4.0)
    kf_scale(body, f, (s, 1.05 * s, s))

# 2 eyes pulse intense
for eye in eyes:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 6.0)
        kf_scale(eye, f, (s, s, s))

# 8 tentacles : each one wave propagated with its own frequency/phase
for tk, (tent_root, tent_segs) in enumerate(tentacles_segments_all):
    # each tentacle has unique frequency for variety
    freq = 3.5 + (tk % 4) * 0.5
    base_phase = tk * 0.4
    for j, seg_p in enumerate(tent_segs):
        seg_phase = j * 0.6
        for f in range(1, FRAMES + 1, 2):
            tt = (f - 1) / (FRAMES - 1)
            wave_y = math.radians(25) * math.sin(tt * math.pi * freq + base_phase - seg_phase)
            wave_z = math.radians(15) * math.cos(tt * math.pi * freq * 1.3 + base_phase - seg_phase)
            kf_rot(seg_p, f, (0, wave_y, wave_z))

# 4 algae sway
for i, ap in enumerate(algae_objs):
    phase = i * 0.6
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(15) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(ap, f, (bend, 0, bend * 0.6))

# 3 fish swim in circles
for fp, fx, fy, fz, idx in fishes:
    r = 1.5
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        a = tt * math.pi * 2.0 + idx * (math.pi * 2 / 3)
        dx = fx + math.cos(a) * r
        dz = fz + math.sin(a) * r
        dy = fy + 0.2 * math.sin(tt * math.pi * 4.0 + idx)
        kf_loc(fp, f, (dx, dy, dz))
        kf_rot(fp, f, (0, -a + math.pi / 2, 0))

# 30 bubbles rise + wobble
for bp, bx, bz, ph in bubbles:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        by = 0.5 + local * 11.0
        wob = math.sin(local * math.pi * 6.0) * 0.20
        kf_loc(bp, f, (bx + wob, by, bz + wob * 0.4))
        s = 0.6 + local * 0.6
        kf_scale(bp, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_octopus] wrote {OUT}")
