"""
proc_robot_humanoid.py — 147e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Robot humanoïde futuriste smooth shaded :
- corps mécanique avec joints articulés
- tête avec 2 yeux LED bleus + 2 antennes
- 2 bras avec articulation épaule + coude + 2 mains à 3 doigts
- 2 jambes avec hanche + genou + cheville + pieds robotique
- plaque pectorale émissive cyclant couleurs
- cables visibles entre joints
- chassis backpack
- sol industrial damier
- 4 lampes plafond
- miroir réfléchissant
- 3 outils outils sur le mur
- 2 lampes spotlight sol
- particules d'énergie autour

Animations multi-axes simultanées :
- robot marche cyclique (legs alternate)
- bras balancent en opposition
- head turns + bob
- yeux pulse intense
- plaque pectorale cycle couleurs
- 4 lampes plafond pulse
- 2 spotlights tournent
- antennes vibration
- 6 particules d'énergie orbitent

Sortie : output/3d/pbr_robot_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_robot_proc.glb"))

random.seed(0xCAFEB3)

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


def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
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
    if smooth:
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
MAT_WALL = make_mat("wall", (0.15, 0.16, 0.20), roughness=0.5,
                     emi=(0.05, 0.06, 0.10), emi_strength=0.2)
MAT_FLOOR_DARK = make_mat("floor_dark", (0.05, 0.05, 0.08), metallic=0.6, roughness=0.05)
MAT_FLOOR_CHECK = make_mat("floor_check", (0.55, 0.55, 0.60), roughness=0.3,
                             emi=(0.18, 0.18, 0.20), emi_strength=0.4)
MAT_ROBOT_WHITE = make_mat("robot_white", (0.85, 0.88, 0.92), metallic=0.65, roughness=0.30,
                             emi=(0.20, 0.22, 0.25), emi_strength=0.25)
MAT_ROBOT_DARK = make_mat("robot_dark", (0.15, 0.18, 0.22), metallic=0.80, roughness=0.30,
                            emi=(0.05, 0.06, 0.10), emi_strength=0.20)
MAT_ROBOT_BLUE = make_mat("robot_blue", (0.15, 0.30, 0.65), metallic=0.55, roughness=0.30,
                            emi=(0.10, 0.20, 0.55), emi_strength=0.30)
MAT_JOINT = make_mat("joint", (0.30, 0.30, 0.35), metallic=0.85, roughness=0.25)
MAT_EYE_BLUE = make_mat("eye_blue", (0.20, 0.50, 1.0), roughness=0.0,
                          emi=(0.20, 0.50, 1.0), emi_strength=12.0)
MAT_CHEST_PLATE = make_mat("chest_plate", (0.20, 0.80, 1.0), roughness=0.0, alpha=0.85,
                             emi=(0.20, 0.80, 1.0), emi_strength=6.0)
MAT_CABLE = make_mat("cable", (0.10, 0.10, 0.12), roughness=0.7)
MAT_CABLE_GLOW = make_mat("cable_glow", (0.30, 1.0, 0.60), roughness=0.0,
                            emi=(0.30, 1.0, 0.60), emi_strength=4.5)
MAT_ANTENNA = make_mat("antenna", (0.55, 0.55, 0.60), metallic=0.90, roughness=0.20)
MAT_ANTENNA_TIP = make_mat("antenna_tip", (1.0, 0.20, 0.10), roughness=0.0,
                             emi=(1.0, 0.20, 0.10), emi_strength=8.0)
MAT_LAMP_LIGHT = make_mat("lamp_light", (1.0, 0.92, 0.75), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.92, 0.75), emi_strength=9.0)
MAT_LAMP_CASE = make_mat("lamp_case", (0.25, 0.25, 0.28), metallic=0.60, roughness=0.40)
MAT_SPOTLIGHT = make_mat("spotlight", (1.0, 0.50, 0.20), roughness=0.0, alpha=0.25,
                           emi=(1.0, 0.50, 0.20), emi_strength=5.0)
MAT_MIRROR = make_mat("mirror", (0.95, 0.95, 0.98), metallic=0.99, roughness=0.02,
                        emi=(0.30, 0.30, 0.35), emi_strength=0.3)
MAT_TOOL_DARK = make_mat("tool_dark", (0.20, 0.20, 0.22), metallic=0.70, roughness=0.35)
MAT_PARTICLE = make_mat("particle", (0.30, 0.95, 1.0), roughness=0.0,
                          emi=(0.30, 0.95, 1.0), emi_strength=8.0)
MAT_TOOL_HANDLE = make_mat("tool_handle", (0.55, 0.20, 0.10), roughness=0.6)

# --- room (industrial garage) -----------------------------------
# floor : 8x8 checkerboard
N_CHECK = 8
CELL = 1.5
for i in range(N_CHECK):
    for j in range(N_CHECK):
        x = -N_CHECK * CELL / 2 + i * CELL + CELL / 2
        z = -N_CHECK * CELL / 2 + j * CELL + CELL / 2
        mat = MAT_FLOOR_CHECK if (i + j) % 2 == 0 else MAT_FLOOR_DARK
        beveled_cube(f"floor_{i}_{j}", (CELL * 0.48, 0.04, CELL * 0.48), bevel_offset=0.02, bevel_segments=2, loc=(x, 0, z), mat=mat)
floor_base = beveled_cube("floor_base", (16, 0.05, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.04, 0), mat=MAT_FLOOR_DARK)

# walls
back_wall = beveled_cube("back_wall", (16, 6, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 3, -7.5), mat=MAT_WALL)
for side, dx in [("L", -8), ("R", 8)]:
    w = beveled_cube(f"wall_{side}", (0.3, 6, 16), bevel_offset=0.05, bevel_segments=2, loc=(dx, 3, 0), mat=MAT_WALL)
ceiling = beveled_cube("ceiling", (16, 0.3, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 6, 0), mat=MAT_WALL)

# --- ROBOT HUMANOID -------------------------------------------------
robot = empty("robot", (0, 0, 0))

# Pelvis (anchor at root)
pelvis = beveled_cube("pelvis", (0.45, 0.30, 0.32), bevel_offset=0.06, bevel_segments=3, loc=(0, 1.10, 0), parent=robot, mat=MAT_ROBOT_DARK)

# Torso (sphere stretched)
torso = smooth_sphere("torso", r=0.40, segs=28, rings=20, loc=(0, 1.65, 0), parent=robot, mat=MAT_ROBOT_WHITE, scale=(1.15, 1.35, 0.85))

# Chest plate (cyan, emissive)
chest_plate = beveled_cube("chest_plate", (0.30, 0.30, 0.05), bevel_offset=0.04, bevel_segments=3, loc=(0, 1.75, 0.30), parent=robot, mat=MAT_CHEST_PLATE)

# Backpack (chassis)
backpack = beveled_cube("backpack", (0.40, 0.55, 0.18), bevel_offset=0.05, bevel_segments=3, loc=(0, 1.65, -0.35), parent=robot, mat=MAT_ROBOT_DARK)
# 2 vents on backpack
for i, dy in enumerate([0.15, -0.15]):
    vent = beveled_cube(f"backpack_vent_{i}", (0.30, 0.04, 0.05), bevel_offset=0.01, bevel_segments=2, loc=(0, 1.65 + dy, -0.50), parent=robot, mat=MAT_CABLE_GLOW)

# Neck
neck = smooth_cone("neck", r1=0.10, r2=0.10, depth=0.15, segs=14, loc=(0, 2.10, 0), parent=robot, mat=MAT_JOINT)
neck.rotation_euler = (math.radians(90), 0, 0)

# Head
head_p = empty("head_p", (0, 2.30, 0), parent=robot)
head = smooth_sphere("head", r=0.25, segs=24, rings=18, loc=(0, 0, 0), parent=head_p, mat=MAT_ROBOT_WHITE, scale=(1.0, 1.05, 0.95))
# Visor (dark strip across eyes)
visor = beveled_cube("visor", (0.32, 0.08, 0.10), bevel_offset=0.03, bevel_segments=3, loc=(0, 0.05, 0.20), parent=head_p, mat=MAT_ROBOT_DARK)
# 2 LED eyes (intense blue)
robot_eyes = []
for side, dz in [("L", 0.08), ("R", -0.08)]:
    eye = smooth_sphere(f"eye_{side}", r=0.05, segs=14, rings=10, loc=(dz, 0.05, 0.24), parent=head_p, mat=MAT_EYE_BLUE)
    robot_eyes.append(eye)
# Mouth grill
mouth_grill = beveled_cube("mouth_grill", (0.15, 0.04, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, -0.10, 0.22), parent=head_p, mat=MAT_ROBOT_DARK)
# 2 antennas (vibration anim)
antennas = []
for side, dz in [("L", 0.12), ("R", -0.12)]:
    ant_p = empty(f"antenna_p_{side}", (0, 0.22, dz), parent=head_p)
    ant = smooth_cone(f"antenna_{side}", r1=0.025, r2=0.015, depth=0.30, segs=10, loc=(0, 0.15, 0), parent=ant_p, mat=MAT_ANTENNA)
    ant.rotation_euler = (math.radians(90), 0, 0)
    tip = smooth_sphere(f"antenna_{side}_tip", r=0.04, segs=12, rings=8, loc=(0, 0.32, 0), parent=ant_p, mat=MAT_ANTENNA_TIP)
    antennas.append(ant_p)

# --- 2 arms (hierarchical : shoulder → upper arm → elbow → forearm → hand) ---
arms_data = []
for side, dz, sign in [("L", 0.42, 1), ("R", -0.42, -1)]:
    # shoulder joint (sphere)
    shoulder = smooth_sphere(f"shoulder_{side}", r=0.13, segs=18, rings=14, loc=(0, 1.90, dz), parent=robot, mat=MAT_JOINT)
    # shoulder_p (pivot for arm rotation)
    shoulder_p = empty(f"shoulder_p_{side}", (0, 1.90, dz), parent=robot)
    # upper arm (cone going down)
    upper_arm = smooth_cone(f"upper_arm_{side}", r1=0.10, r2=0.08, depth=0.45, segs=14, loc=(0, -0.225, 0), parent=shoulder_p, mat=MAT_ROBOT_WHITE)
    # elbow joint
    elbow = smooth_sphere(f"elbow_{side}", r=0.10, segs=16, rings=12, loc=(0, -0.50, 0), parent=shoulder_p, mat=MAT_JOINT)
    # elbow_p
    elbow_p = empty(f"elbow_p_{side}", (0, -0.50, 0), parent=shoulder_p)
    # forearm
    forearm = smooth_cone(f"forearm_{side}", r1=0.08, r2=0.07, depth=0.40, segs=14, loc=(0, -0.20, 0), parent=elbow_p, mat=MAT_ROBOT_WHITE)
    # wrist
    wrist = smooth_sphere(f"wrist_{side}", r=0.07, segs=14, rings=10, loc=(0, -0.42, 0), parent=elbow_p, mat=MAT_JOINT)
    # hand (palm + 3 fingers)
    hand_p = empty(f"hand_p_{side}", (0, -0.50, 0), parent=elbow_p)
    palm = beveled_cube(f"palm_{side}", (0.06, 0.12, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(0, -0.08, 0), parent=hand_p, mat=MAT_ROBOT_WHITE)
    # 3 fingers
    for k in range(3):
        fz = -0.04 + k * 0.04
        # 2 segments per finger
        for j in range(2):
            jy = -0.18 - j * 0.06
            finger = beveled_cube(f"finger_{side}_{k}_{j}", (0.03, 0.06, 0.03), bevel_offset=0.005, bevel_segments=2, loc=(0, jy, fz), parent=hand_p, mat=MAT_ROBOT_DARK)
    # thumb
    thumb_p = empty(f"thumb_p_{side}", (0, -0.10, 0.06), parent=hand_p)
    thumb_p.rotation_euler = (0, 0, math.radians(35))
    for j in range(2):
        jy = -0.04 - j * 0.05
        thumb = beveled_cube(f"thumb_{side}_{j}", (0.03, 0.05, 0.03), bevel_offset=0.005, bevel_segments=2, loc=(0, jy, 0), parent=thumb_p, mat=MAT_ROBOT_DARK)
    # cable visible on upper arm
    cable = smooth_cone(f"cable_{side}", r1=0.02, r2=0.02, depth=0.45, segs=8, loc=(0.08, -0.225, 0), parent=shoulder_p, mat=MAT_CABLE)
    cable_glow = smooth_cone(f"cable_glow_{side}", r1=0.012, r2=0.012, depth=0.45, segs=8, loc=(0.08, -0.225, 0), parent=shoulder_p, mat=MAT_CABLE_GLOW)
    arms_data.append((shoulder_p, elbow_p))

# --- 2 legs (hierarchical : hip → thigh → knee → shin → ankle → foot) ---
legs_data = []
for side, dz, sign in [("L", 0.18, 1), ("R", -0.18, -1)]:
    # hip joint
    hip = smooth_sphere(f"hip_{side}", r=0.13, segs=18, rings=14, loc=(0, 0.90, dz), parent=robot, mat=MAT_JOINT)
    # hip_p (pivot for walking)
    hip_p = empty(f"hip_p_{side}", (0, 0.90, dz), parent=robot)
    # thigh
    thigh = smooth_cone(f"thigh_{side}", r1=0.12, r2=0.10, depth=0.50, segs=14, loc=(0, -0.25, 0), parent=hip_p, mat=MAT_ROBOT_WHITE)
    # knee
    knee = smooth_sphere(f"knee_{side}", r=0.11, segs=16, rings=12, loc=(0, -0.55, 0), parent=hip_p, mat=MAT_JOINT)
    knee_p = empty(f"knee_p_{side}", (0, -0.55, 0), parent=hip_p)
    # shin
    shin = smooth_cone(f"shin_{side}", r1=0.10, r2=0.08, depth=0.45, segs=14, loc=(0, -0.225, 0), parent=knee_p, mat=MAT_ROBOT_WHITE)
    # ankle
    ankle = smooth_sphere(f"ankle_{side}", r=0.08, segs=14, rings=10, loc=(0, -0.50, 0), parent=knee_p, mat=MAT_JOINT)
    # foot (rectangular)
    foot = beveled_cube(f"foot_{side}", (0.16, 0.06, 0.32), bevel_offset=0.04, bevel_segments=3, loc=(0, -0.58, 0.06), parent=knee_p, mat=MAT_ROBOT_DARK)
    # cable on thigh
    cable = smooth_cone(f"leg_cable_{side}", r1=0.018, r2=0.018, depth=0.5, segs=8, loc=(0.10, -0.25, 0), parent=hip_p, mat=MAT_CABLE_GLOW)
    legs_data.append((hip_p, knee_p))

# --- 4 ceiling lamps ----------------------------------------
ceiling_lamps = []
for i, (lx, lz) in enumerate([(-4, 4), (4, 4), (-4, -4), (4, -4)]):
    lp = empty(f"clamp_{i}", (lx, 5.8, lz))
    rod = smooth_cone(f"clamp_{i}_rod", r1=0.04, r2=0.04, depth=0.40, segs=10, loc=(0, -0.20, 0), parent=lp, mat=MAT_LAMP_CASE)
    rod.rotation_euler = (math.radians(90), 0, 0)
    shade = smooth_cone(f"clamp_{i}_shade", r1=0.30, r2=0.18, depth=0.25, segs=20, loc=(0, -0.45, 0), parent=lp, mat=MAT_LAMP_CASE)
    shade.rotation_euler = (math.radians(180), 0, 0)
    bulb = smooth_sphere(f"clamp_{i}_bulb", r=0.18, segs=20, rings=14, loc=(0, -0.55, 0), parent=lp, mat=MAT_LAMP_LIGHT)
    ceiling_lamps.append(bulb)

# --- 2 spotlights on floor (illuminate robot dramatically) ----
spotlight_beams = []
for i, (sx, sz) in enumerate([(-3, 3), (3, 3)]):
    sp_p = empty(f"spot_p_{i}", (sx, 0.3, sz))
    sp_p.rotation_euler = (0, math.radians(-25 if i == 0 else 25), 0)
    # base
    base = smooth_cone(f"spot_{i}_base", r1=0.30, r2=0.25, depth=0.30, segs=14, loc=(0, 0, 0), parent=sp_p, mat=MAT_LAMP_CASE)
    base.rotation_euler = (math.radians(90), 0, 0)
    # beam (large cone alpha)
    beam_p = empty(f"spot_{i}_beam_p", (0, 0.3, 0), parent=sp_p)
    beam = smooth_cone(f"spot_{i}_beam", r1=0.05, r2=2.0, depth=8.0, segs=18, loc=(0, 4.0, 0), parent=beam_p, mat=MAT_SPOTLIGHT)
    spotlight_beams.append(beam_p)

# --- 3 tools on wall ----------------------------------------
for i, (tx, tz) in enumerate([(-3, -7.3), (-1.5, -7.3), (0, -7.3)]):
    tp = empty(f"tool_{i}", (tx, 3.5 + i * 0.5, tz))
    handle = beveled_cube(f"tool_{i}_handle", (0.06, 0.5, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0), parent=tp, mat=MAT_TOOL_HANDLE)
    head_tool = beveled_cube(f"tool_{i}_head", (0.12, 0.10, 0.08), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.30, 0), parent=tp, mat=MAT_TOOL_DARK)

# --- mirror on back wall ------------------------------------
mirror = beveled_cube("mirror", (2.5, 0.05, 1.8), bevel_offset=0.08, bevel_segments=3, loc=(5, 2.5, -7.3), parent=None, mat=MAT_MIRROR)

# --- 6 particules d'énergie autour du robot ---------------
particles = []
for i in range(6):
    a = i * (math.pi * 2 / 6)
    px = math.cos(a) * 1.5
    py = 1.5 + math.sin(a) * 0.5
    pz = math.sin(a) * 1.5
    p = smooth_sphere(f"particle_{i}", r=0.08, segs=12, rings=10, loc=(px, py, pz), mat=MAT_PARTICLE)
    particles.append((p, a))

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

# robot subtle bob + slow rotate (showcase pose)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    by = 0 + 0.05 * math.sin(tt * math.pi * 4.0)
    rotY = math.radians(20) * math.sin(tt * math.pi * 2.0)
    kf_loc(robot, f, (0, by, 0))
    kf_rot(robot, f, (0, rotY, 0))

# 2 legs alternate walking
for i, (hip_p, knee_p) in enumerate(legs_data):
    sign = 1 if i == 0 else -1
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # hip swing forward/back
        hip_angle = math.radians(15) * math.sin(tt * math.pi * 6.0 + (math.pi if i == 1 else 0))
        kf_rot(hip_p, f, (0, 0, hip_angle))
        # knee bend (more during forward swing)
        knee_angle = math.radians(-25) * max(0, math.sin(tt * math.pi * 6.0 + (math.pi if i == 1 else 0)))
        kf_rot(knee_p, f, (0, 0, knee_angle))

# 2 arms swing in opposition to legs
for i, (shoulder_p, elbow_p) in enumerate(arms_data):
    sign = 1 if i == 0 else -1
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # arm swings opposite of leg
        arm_angle = math.radians(20) * math.sin(tt * math.pi * 6.0 + (0 if i == 1 else math.pi))
        kf_rot(shoulder_p, f, (0, 0, arm_angle))
        # elbow slight bend
        elbow_angle = math.radians(-15) * (1 + math.sin(tt * math.pi * 6.0)) * 0.5
        kf_rot(elbow_p, f, (0, 0, elbow_angle))

# head turns + bob
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    head_y = math.radians(15) * math.sin(tt * math.pi * 3.0)
    head_x = math.radians(5) * math.cos(tt * math.pi * 4.0)
    kf_rot(head_p, f, (head_x, head_y, 0))

# 2 eyes pulse intense blue
for eye in robot_eyes:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 8.0)
        kf_scale(eye, f, (s, s, s))

# chest plate pulse strong
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0)
    kf_scale(chest_plate, f, (s, s, 1.0))

# 2 antennas vibrate
for ant_p in antennas:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        vib = math.radians(5) * math.sin(tt * math.pi * 20.0)
        kf_rot(ant_p, f, (vib, vib * 0.5, 0))

# 4 ceiling lamps pulse
for i, bulb in enumerate(ceiling_lamps):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(bulb, f, (s, s, s))

# 2 spotlights rotate slowly
for i, beam_p in enumerate(spotlight_beams):
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        angle = math.radians(30) * math.sin(tt * math.pi * 1.5 + i * math.pi)
        kf_rot(beam_p, f, (0, angle, 0))

# 6 particules orbitent autour du robot
for p, a0 in particles:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 3.0
        px = math.cos(angle) * 1.5
        py = 1.5 + math.sin(tt * math.pi * 4.0 + a0) * 0.5
        pz = math.sin(angle) * 1.5
        kf_loc(p, f, (px, py, pz))
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 8.0 + a0)
        kf_scale(p, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_robot] wrote {OUT}")
