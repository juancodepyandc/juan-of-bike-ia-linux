"""
proc_clock_interior_mechanism.py — 169e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Intérieur mécanisme horloge géant avec engrenages synchronisés :
- 12 grands engrenages dorés bevelés tailles variées s'engrenant
- axe central + roue d'échappement
- ancre + balancier oscillant
- chaîne tirants + 4 ressorts spiralés
- 6 masselottes spin
- plaques cuivre arrière
- 4 lampes émissives
- cadrant arrière (12 chiffres + transparent)
- 30 ressorts spiralés petits
- pièces démontées établi
- bouts cuivre + verre dôme
- ciel atelier

Animations multi-axes simultanées :
- 12 engrenages rotations rates synchronisées (ratios diviseurs/multiplicateurs)
- balancier oscille 2 Hz (±25°)
- ancre tic-tac 2 Hz aligné balancier
- échappement avance step
- 4 ressorts compress
- 6 masselottes spin Z
- lampes pulse

Sortie : output/3d/pbr_clockmech_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_clockmech_proc.glb"))

random.seed(0xC10CCE)


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
MAT_WALL = make_mat("wall_cu", (0.35, 0.22, 0.15), roughness=0.85, emi=(0.18, 0.10, 0.06), emi_strength=0.3)
MAT_FLOOR = make_mat("floor", (0.18, 0.12, 0.08), roughness=0.85)
MAT_BRASS = make_mat("brass", (0.90, 0.70, 0.30), metallic=0.95, roughness=0.20, emi=(0.40, 0.30, 0.10), emi_strength=0.5)
MAT_BRASS_BRIGHT = make_mat("brass_bright", (1.0, 0.85, 0.40), metallic=0.95, roughness=0.15, emi=(0.55, 0.40, 0.15), emi_strength=0.8)
MAT_BRASS_DARK = make_mat("brass_dark", (0.55, 0.40, 0.18), metallic=0.85, roughness=0.40)
MAT_COPPER = make_mat("copper", (0.85, 0.50, 0.30), metallic=0.85, roughness=0.30, emi=(0.30, 0.18, 0.12), emi_strength=0.3)
MAT_IRON = make_mat("iron", (0.40, 0.35, 0.30), metallic=0.85, roughness=0.55)
MAT_STEEL = make_mat("steel", (0.65, 0.65, 0.70), metallic=0.95, roughness=0.20)
MAT_GLASS = make_mat("glass", (0.90, 0.95, 1.0), roughness=0.05, alpha=0.35, emi=(0.40, 0.45, 0.50), emi_strength=0.5)
MAT_LAMP = make_mat("lamp", (1.0, 0.85, 0.45), roughness=0.0, emi=(1.0, 0.85, 0.45), emi_strength=14.0)
MAT_DIAL_FACE = make_mat("dial_face", (0.92, 0.88, 0.75), roughness=0.40, alpha=0.65, emi=(0.45, 0.40, 0.30), emi_strength=1.2)
MAT_NUMERAL = make_mat("numeral", (0.15, 0.10, 0.05), metallic=0.30, roughness=0.40)
MAT_RUBY = make_mat("ruby", (1.0, 0.15, 0.30), roughness=0.05, emi=(1.0, 0.15, 0.30), emi_strength=8.0)


# --- backdrop : workshop ----------------------------------------------------
back_wall = beveled_cube("back_wall", (14, 0.2, 9), bevel_offset=0.05, bevel_segments=2, loc=(0, 4.5, 3.5), mat=MAT_WALL)
floor = beveled_cube("floor", (14, 0.1, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_FLOOR)

# back dial face (transparent with 12 numerals visible)
dial_p = empty("dial_p", (0, 5, 3.4))
smooth_cone("dial_face", r1=2.5, r2=2.5, depth=0.10, segs=32, loc=(0, 0, 0), parent=dial_p, mat=MAT_DIAL_FACE)
# 12 numerals
for n in range(12):
    na = -math.pi / 2 + n * (math.pi * 2 / 12)
    nx = math.cos(na) * 2.0
    ny = math.sin(na) * 2.0
    beveled_cube(f"num_{n}", (0.20, 0.30, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(nx, ny, 0.10), parent=dial_p, mat=MAT_NUMERAL)
# dial frame
smooth_cone("dial_frame", r1=2.7, r2=2.7, depth=0.20, segs=32, loc=(0, 0, -0.05), parent=dial_p, mat=MAT_BRASS_DARK)
# dial outer ring
smooth_cone("dial_outer", r1=2.85, r2=2.85, depth=0.10, segs=32, loc=(0, 0, 0), parent=dial_p, mat=MAT_BRASS_BRIGHT)


# --- 12 ENGRENAGES (gears) configurations ------------------------------
# Each gear : (cx, cy, cz, radius, teeth, base_speed)
# speed ratios designed for visual sync
GEAR_CONFIGS = [
    (0, 3, 1.5, 0.90, 24, 1.0),       # G0 main large center
    (-1.6, 3, 1.5, 0.55, 14, -1.71),  # G1 left meshing with G0
    (1.6, 3, 1.5, 0.55, 14, -1.71),   # G2 right meshing with G0
    (-2.6, 3, 1.5, 0.35, 9, 2.69),   # G3 top-left
    (2.6, 3, 1.5, 0.35, 9, 2.69),    # G4 top-right
    (0, 4.6, 1.5, 0.45, 11, -2.0),   # G5 top center
    (0, 1.4, 1.5, 0.65, 16, -1.38),  # G6 bottom center (large)
    (-1.5, 1.4, 1.5, 0.30, 8, 3.0),  # G7
    (1.5, 1.4, 1.5, 0.30, 8, 3.0),   # G8
    (-3.5, 2.5, 1.5, 0.40, 10, 2.0),  # G9 outer left
    (3.5, 2.5, 1.5, 0.40, 10, 2.0),   # G10 outer right
    (0, 6.5, 1.5, 0.35, 9, -2.5),     # G11 top high (escapement wheel)
]
gears = []
for gi, (gx, gy, gz, gr, teeth, gspd) in enumerate(GEAR_CONFIGS):
    gp = empty(f"gear_p_{gi}", (gx, gy, gz))
    # body cylinder
    body = smooth_cone(f"gear_body_{gi}", r1=gr, r2=gr, depth=0.15, segs=24, loc=(0, 0, 0), parent=gp, mat=MAT_BRASS)
    body.rotation_euler = (math.radians(90), 0, 0)
    # teeth
    for tk in range(teeth):
        ta = tk * (math.pi * 2 / teeth)
        tx = math.cos(ta) * (gr + 0.07)
        ty = math.sin(ta) * (gr + 0.07)
        tooth = beveled_cube(f"gear_{gi}_t_{tk}", (0.10, 0.12, 0.13), bevel_offset=0.02, bevel_segments=2, loc=(tx, ty, 0), parent=gp, mat=MAT_BRASS_DARK)
        tooth.rotation_euler = (0, 0, ta)
    # central pin
    smooth_sphere(f"gear_{gi}_pin", r=0.08, segs=14, rings=10, loc=(0, 0, 0), parent=gp, mat=MAT_BRASS_BRIGHT)
    # decorative spokes (6 lines from center to rim)
    for sk in range(6):
        sa = sk * (math.pi * 2 / 6)
        spoke = beveled_cube(f"gear_{gi}_sp_{sk}", (0.06, gr * 0.85, 0.06), bevel_offset=0.01, bevel_segments=2, loc=(math.cos(sa) * gr * 0.40, math.sin(sa) * gr * 0.40, 0), parent=gp, mat=MAT_BRASS_DARK)
        spoke.rotation_euler = (0, 0, sa)
    gears.append({"p": gp, "spd": gspd, "phase": gi * 0.10})


# --- ANCRE + BALANCIER -------------------------------------------------
# anchor (escapement lever)
anchor_p = empty("anchor_p", (0, 6.5, 1.7))
# anchor body (Y shape)
beveled_cube("anchor_body", (1.2, 0.10, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=anchor_p, mat=MAT_STEEL)
# 2 pallets at ends
for pk, px in [(0, -0.55), (1, 0.55)]:
    smooth_cone(f"anchor_pal_{pk}", r1=0.10, r2=0.06, depth=0.20, segs=10, loc=(px, -0.15, 0), parent=anchor_p, mat=MAT_STEEL)
# center pivot
smooth_sphere("anchor_pivot", r=0.10, segs=14, rings=10, loc=(0, 0, 0), parent=anchor_p, mat=MAT_BRASS_BRIGHT)

# BALANCIER (pendulum)
pendulum_p = empty("pendulum_p", (-4, 5, 2))
# rod
rod = smooth_cone("pend_rod", r1=0.04, r2=0.04, depth=3.0, segs=8, loc=(0, -1.5, 0), parent=pendulum_p, mat=MAT_BRASS_DARK)
# bob (round weight at bottom)
smooth_sphere("pend_bob", r=0.40, segs=20, rings=14, loc=(0, -3.0, 0), parent=pendulum_p, mat=MAT_BRASS, scale=(1.0, 0.85, 1.0))
# decorative top
smooth_sphere("pend_top", r=0.12, segs=14, rings=10, loc=(0, 0, 0), parent=pendulum_p, mat=MAT_BRASS_BRIGHT)
# ruby jewel in center bob
smooth_sphere("pend_ruby", r=0.10, segs=12, rings=8, loc=(0, -3.0, 0.30), parent=pendulum_p, mat=MAT_RUBY)


# --- 4 RESSORTS SPIRALÉS (main springs) -----------------------------
# spiral spring using N segments
def make_spring(name, base_loc, base_radius=0.25, height=0.6, turns=4, n_segs=60, mat=MAT_STEEL):
    sp_p = empty(name, base_loc)
    for sg in range(n_segs):
        t = sg / n_segs
        ang = t * turns * 2 * math.pi
        x = math.cos(ang) * base_radius
        z = math.sin(ang) * base_radius
        y = (t - 0.5) * height
        smooth_sphere(f"{name}_s_{sg}", r=0.025, segs=8, rings=6, loc=(x, y, z), parent=sp_p, mat=mat)
    return sp_p

springs = []
SPRING_POSITIONS = [(-5, 3, 1.7), (5, 3, 1.7), (-5, 1, 1.7), (5, 1, 1.7)]
for si, sloc in enumerate(SPRING_POSITIONS):
    spring_p = make_spring(f"spring_{si}", sloc, base_radius=0.30, height=0.8, turns=5, n_segs=40, mat=MAT_STEEL)
    springs.append({"p": spring_p, "phase": si * 0.4})


# --- 6 MASSELOTTES (counterweights) qui tournent --------------------
weights = []
WEIGHT_POSITIONS = [(-5, 4.5, 1.7), (5, 4.5, 1.7), (-5, 6, 1.7), (5, 6, 1.7), (-6, 3, 1.7), (6, 3, 1.7)]
for wi, (wx, wy, wz) in enumerate(WEIGHT_POSITIONS):
    wp = empty(f"weight_{wi}_p", (wx, wy, wz))
    # main weight (cylinder)
    weight_body = smooth_cone(f"weight_{wi}_body", r1=0.20, r2=0.20, depth=0.20, segs=14, loc=(0, 0, 0), parent=wp, mat=MAT_BRASS)
    weight_body.rotation_euler = (math.radians(90), 0, 0)
    # ornament
    smooth_sphere(f"weight_{wi}_ornament", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=wp, mat=MAT_BRASS_BRIGHT)
    # 4 small protrusions
    for pk in range(4):
        pa = pk * (math.pi * 2 / 4)
        smooth_sphere(f"weight_{wi}_p_{pk}", r=0.05, segs=10, rings=6, loc=(math.cos(pa) * 0.22, math.sin(pa) * 0.22, 0), parent=wp, mat=MAT_BRASS_DARK)
    weights.append({"p": wp, "phase": wi * 0.35, "spd": (1 if wi % 2 == 0 else -1) * (1 + wi * 0.3)})


# --- chain (links connecting some gears) ------------------------------
# simple decorative chain at the bottom
for ci in range(10):
    cx = -3 + ci * 0.6
    chain_link = beveled_cube(f"chain_{ci}", (0.10, 0.15, 0.05), bevel_offset=0.02, bevel_segments=2, loc=(cx, 0.30, 1.6), mat=MAT_IRON)
    chain_link.rotation_euler = (0, 0, math.radians(45 if ci % 2 == 0 else -45))


# --- 4 LAMPES émissives ------------------------------------------------
lamps = []
LAMP_POSITIONS = [(-5, 7, 1.5), (5, 7, 1.5), (-5, 0.5, 1.5), (5, 0.5, 1.5)]
for li, (lx, ly, lz) in enumerate(LAMP_POSITIONS):
    lp = empty(f"lamp_{li}_p", (lx, ly, lz))
    # housing
    smooth_cone(f"lamp_{li}_h", r1=0.20, r2=0.15, depth=0.30, segs=12, loc=(0, 0, 0), parent=lp, mat=MAT_BRASS_DARK)
    # glow
    glow = smooth_sphere(f"lamp_{li}_glow", r=0.15, segs=14, rings=10, loc=(0, 0.10, 0), parent=lp, mat=MAT_LAMP)
    lamps.append({"p": lp, "glow": glow, "phase": li * 0.30})


# --- 30 RESSORTS SPIRALÉS PETITS (background detail) --------------
# Just decorative small coils on workbench
for sk in range(30):
    sx = random.uniform(-6, 6)
    sy = random.uniform(0.30, 1.0)
    sz = random.uniform(2.5, 3.2)
    # small coil
    for cs in range(8):
        ang = cs * (math.pi * 2 / 8) + sk * 0.15
        coil = smooth_sphere(f"smcoil_{sk}_{cs}", r=0.015, segs=6, rings=4, loc=(sx + math.cos(ang) * 0.08, sy + cs * 0.015 - 0.05, sz + math.sin(ang) * 0.08), mat=MAT_STEEL)


# --- établi (workbench) avec pièces démontées -------------------------
bench_p = empty("bench_p", (0, 0, 2.8))
# top
beveled_cube("bench_top", (8, 0.10, 1.5), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.85, 0), parent=bench_p, mat=MAT_WALL)
# 4 legs
for lx in [-3.5, -1.5, 1.5, 3.5]:
    smooth_cone(f"bench_leg_{lx}", r1=0.10, r2=0.08, depth=0.85, segs=8, loc=(lx, 0.42, 0), parent=bench_p, mat=MAT_WALL)
# small disassembled gears on bench
for dk in range(6):
    dx = -3 + dk * 1.0
    smooth_cone(f"bench_gear_{dk}", r1=0.18, r2=0.18, depth=0.06, segs=14, loc=(dx, 0.95, 0.3), parent=bench_p, mat=MAT_BRASS).rotation_euler = (math.radians(90), 0, 0)


# --- verre dôme (transparent over the mechanism) ---------------------
dome_p = empty("dome_p", (0, 3, 1.5))
smooth_sphere("dome_glass", r=5.5, segs=28, rings=20, loc=(0, 0, 0), parent=dome_p, mat=MAT_GLASS, scale=(1.4, 1.4, 0.5))


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

    # 12 gears rotate synchronized (rates per ratios)
    for gd in gears:
        ang = tt * 2 * math.pi * gd["spd"] * 2
        kf(gd["p"], f, "rotation_euler", (math.radians(90), 0, ang))

    # ANCRE (anchor) : oscillates ±5° at 2 Hz
    anchor_swing = math.radians(8) * math.sin(2 * math.pi * tt * 4)
    kf(anchor_p, f, "rotation_euler", (0, 0, anchor_swing))

    # BALANCIER (pendulum) : oscillates ±20° at 2 Hz (same rate)
    pend_swing = math.radians(20) * math.sin(2 * math.pi * tt * 4)
    kf(pendulum_p, f, "rotation_euler", (0, 0, pend_swing))

    # 4 springs compress/expand (scale Y)
    for sd in springs:
        ph = sd["phase"]
        sc_y = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(sd["p"], f, "scale", (1.0, sc_y, 1.0))

    # 6 weights spin
    for wd in weights:
        ph = wd["phase"]
        spd = wd["spd"]
        kf(wd["p"], f, "rotation_euler", (math.radians(90), 0, math.radians(360 * tt * spd + ph * 30)))

    # 4 lamps pulse
    for ld in lamps:
        ph = ld["phase"]
        ps = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(ld["glow"], f, "scale", (ps, ps, ps))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_clock_interior_mechanism] wrote {OUT}")
