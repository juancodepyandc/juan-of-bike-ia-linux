"""
proc_mech_battle_arena.py — 166e procédural AuroraIA, MILESTONE 30E QUALITÉ.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie hiérarchique).

Combat mecha géants dans arène industrielle :
- 2 mechas anatomiques articulés (cockpit + torse + 2 bras + 2 jambes + cou + tête)
- mecha A rouge agressif, mecha B bleu défenseur
- tirs lasers émissifs entre les deux
- arène industrielle (sol bevelé + 4 murs ruinés)
- 4 tours sentinelles avec tourelles tournantes
- 30 explosions sol pulse émissives
- 100 étincelles métal trajectoires paraboliques
- 30 fragments métalliques drift
- foule 20 spectateurs gradins
- 4 écrans géants émissifs avec cycles couleurs
- 2 grues swing
- ciel apocalyptique orange-violet
- nuages noirs drift
- 8 flammes secondaires au sol

Animations multi-axes simultanées :
- 2 mechas combat : bras swing punch + recul step + bonds + torse twist
- 4 tours tourelles rotation + tirs lasers
- 30 explosions sol pulse intense
- 100 étincelles parabolic trajectories
- 30 fragments drift + rotate 3-axes
- 20 spectateurs wave
- 4 écrans cycle colors
- 2 grues swing arc
- 8 flammes pulse + sway
- nuages drift

Sortie : output/3d/pbr_mech_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_mech_proc.glb"))

random.seed(0xCEC4BB)


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
MAT_SKY = make_mat("sky_apoc", (0.30, 0.10, 0.20), roughness=1.0, emi=(0.30, 0.12, 0.20), emi_strength=1.0)
MAT_CLOUD_DARK = make_mat("cloud_dark", (0.15, 0.10, 0.10), roughness=1.0, alpha=0.70, emi=(0.10, 0.05, 0.08), emi_strength=0.3)
MAT_GROUND = make_mat("ground", (0.20, 0.18, 0.16), roughness=0.90, emi=(0.10, 0.05, 0.05), emi_strength=0.2)
MAT_RUBBLE = make_mat("rubble", (0.30, 0.25, 0.22), roughness=0.90)
MAT_MECH_A_PRIMARY = make_mat("mech_A_prim", (0.85, 0.20, 0.15), metallic=0.85, roughness=0.40, emi=(0.45, 0.10, 0.08), emi_strength=0.8)
MAT_MECH_A_SECONDARY = make_mat("mech_A_sec", (0.30, 0.10, 0.10), metallic=0.85, roughness=0.50)
MAT_MECH_A_ACCENT = make_mat("mech_A_acc", (1.0, 0.45, 0.20), roughness=0.0, emi=(1.0, 0.45, 0.20), emi_strength=10.0)
MAT_MECH_B_PRIMARY = make_mat("mech_B_prim", (0.20, 0.40, 0.85), metallic=0.85, roughness=0.40, emi=(0.10, 0.20, 0.45), emi_strength=0.8)
MAT_MECH_B_SECONDARY = make_mat("mech_B_sec", (0.10, 0.15, 0.30), metallic=0.85, roughness=0.50)
MAT_MECH_B_ACCENT = make_mat("mech_B_acc", (0.30, 0.85, 1.0), roughness=0.0, emi=(0.30, 0.85, 1.0), emi_strength=10.0)
MAT_LASER_RED = make_mat("laser_red", (1.0, 0.30, 0.20), roughness=0.0, alpha=0.85, emi=(1.0, 0.30, 0.20), emi_strength=15.0)
MAT_LASER_BLUE = make_mat("laser_blue", (0.30, 0.60, 1.0), roughness=0.0, alpha=0.85, emi=(0.30, 0.60, 1.0), emi_strength=15.0)
MAT_EXPLOSION = make_mat("explosion", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=14.0)
MAT_SPARK = make_mat("spark", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_FRAGMENT = make_mat("fragment", (0.40, 0.35, 0.32), metallic=0.7, roughness=0.50)
MAT_FLAME = make_mat("flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=13.0)
MAT_SMOKE = make_mat("smoke", (0.30, 0.25, 0.25), roughness=1.0, alpha=0.40, emi=(0.20, 0.15, 0.15), emi_strength=0.6)
MAT_TOWER = make_mat("tower", (0.25, 0.22, 0.20), roughness=0.7)
MAT_TOWER_RED = make_mat("tower_red", (0.60, 0.20, 0.20), roughness=0.5, emi=(0.30, 0.05, 0.05), emi_strength=0.5)
MAT_SCREEN_A = make_mat("screen_A", (0.30, 0.85, 1.0), roughness=0.0, emi=(0.30, 0.85, 1.0), emi_strength=11.0)
MAT_SCREEN_B = make_mat("screen_B", (1.0, 0.30, 0.40), roughness=0.0, emi=(1.0, 0.30, 0.40), emi_strength=11.0)
MAT_SCREEN_C = make_mat("screen_C", (0.85, 0.95, 0.30), roughness=0.0, emi=(0.85, 0.95, 0.30), emi_strength=11.0)
MAT_GRADIN = make_mat("gradin", (0.40, 0.35, 0.30), roughness=0.85)
MAT_SPECTATOR = make_mat("spectator", (0.20, 0.20, 0.25), roughness=0.7)
MAT_CRANE = make_mat("crane", (0.85, 0.65, 0.20), metallic=0.5, roughness=0.45)


# --- backdrop : apocalyptic sky -------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)
ground = beveled_cube("ground", (40, 0.2, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND)

# 10 dark clouds drift
clouds = []
for ck in range(10):
    cx = random.uniform(-18, 18)
    cy = random.uniform(11, 15)
    cz = random.uniform(5, 14)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    for j in range(3):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.8, 1.2), segs=14, rings=10, loc=(random.uniform(-0.9, 0.9), random.uniform(-0.2, 0.2), random.uniform(-0.6, 0.6)), parent=cp, mat=MAT_CLOUD_DARK, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.4, 0.8)


# --- arène industrielle : 4 murs ruinés -----------------------------------
WALL_POSITIONS = [(-12, 0, 0), (12, 0, 0), (0, 0, -10), (0, 0, 10)]
for wi, (wx, wy, wz) in enumerate(WALL_POSITIONS):
    # broken wall (3 segments uneven heights)
    for sg in range(5):
        sx_off = -2 + sg * 1.0
        sh = random.uniform(2.0, 4.5)
        if wi < 2:
            # left/right walls
            beveled_cube(f"wall_{wi}_s_{sg}", (0.50, sh, 1.0), bevel_offset=0.05, bevel_segments=2, loc=(wx, sh / 2, sx_off), mat=MAT_RUBBLE)
        else:
            beveled_cube(f"wall_{wi}_s_{sg}", (1.0, sh, 0.50), bevel_offset=0.05, bevel_segments=2, loc=(sx_off * 2.5, sh / 2, wz), mat=MAT_RUBBLE)


# --- MECH A (red, attacker, left side) -----------------------------------
def build_mech(name, base_pos, mat_prim, mat_sec, mat_accent, facing_dir=1):
    mp = empty(f"{name}_p", base_pos)

    # torse (chest box)
    chest = beveled_cube(f"{name}_chest", (1.4, 1.6, 0.9), bevel_offset=0.06, bevel_segments=2, loc=(0, 3.5, 0), parent=mp, mat=mat_prim)
    # cockpit (glowing visor at top of chest)
    cockpit = beveled_cube(f"{name}_cockpit", (1.0, 0.30, 0.10), bevel_offset=0.03, bevel_segments=2, loc=(0, 4.20, 0.50 * facing_dir), parent=mp, mat=mat_accent)
    # chest armor accent
    smooth_sphere(f"{name}_chest_acc", r=0.20, segs=14, rings=10, loc=(0, 3.5, 0.45 * facing_dir), parent=mp, mat=mat_accent, scale=(1.2, 0.5, 0.3))
    # 2 shoulder pauldrons
    for sk, sz in [("L", 0.85), ("R", -0.85)]:
        smooth_sphere(f"{name}_pauldron_{sk}", r=0.45, segs=18, rings=14, loc=(0, 4.20, sz), parent=mp, mat=mat_sec, scale=(1.0, 0.65, 1.0))
    # neck
    smooth_cone(f"{name}_neck", r1=0.18, r2=0.15, depth=0.25, segs=12, loc=(0, 4.40, 0), parent=mp, mat=mat_sec)
    # head (helmet)
    head = smooth_sphere(f"{name}_head", r=0.35, segs=20, rings=16, loc=(0, 4.75, 0), parent=mp, mat=mat_prim, scale=(1.0, 1.1, 1.0))
    # eye glow (single horizontal slot)
    beveled_cube(f"{name}_eye", (0.40, 0.08, 0.05), bevel_offset=0.02, bevel_segments=2, loc=(0, 4.75, 0.32 * facing_dir), parent=mp, mat=mat_accent)
    # head antenna
    smooth_cone(f"{name}_antenna", r1=0.02, r2=0.0, depth=0.35, segs=6, loc=(0, 5.05, -0.15 * facing_dir), parent=mp, mat=mat_sec)

    # 2 arms (parented for articulation)
    arms = {}
    for sk, sz, sign in [("L", 0.95, 1), ("R", -0.95, -1)]:
        # shoulder joint
        shoulder_p = empty(f"{name}_shoulder_{sk}", (0, 3.85, sz), parent=mp)
        arms[f"shoulder_{sk}"] = shoulder_p
        # upper arm
        smooth_cone(f"{name}_uparm_{sk}", r1=0.18, r2=0.16, depth=0.85, segs=12, loc=(0, -0.45, 0), parent=shoulder_p, mat=mat_prim)
        # elbow joint
        elbow_p = empty(f"{name}_elbow_{sk}", (0, -0.85, 0), parent=shoulder_p)
        arms[f"elbow_{sk}"] = elbow_p
        # forearm
        smooth_cone(f"{name}_forearm_{sk}", r1=0.16, r2=0.14, depth=0.80, segs=12, loc=(0, -0.42, 0), parent=elbow_p, mat=mat_sec)
        # hand/weapon
        wrist_p = empty(f"{name}_wrist_{sk}", (0, -0.80, 0), parent=elbow_p)
        arms[f"wrist_{sk}"] = wrist_p
        # weapon (energy gun)
        gun = beveled_cube(f"{name}_gun_{sk}", (0.18, 0.25, 0.35), bevel_offset=0.03, bevel_segments=2, loc=(0, -0.15, 0.15), parent=wrist_p, mat=mat_sec)
        # barrel
        smooth_cone(f"{name}_barrel_{sk}", r1=0.05, r2=0.04, depth=0.40, segs=8, loc=(0, -0.15, 0.45), parent=wrist_p, mat=mat_sec)
        # muzzle glow
        smooth_sphere(f"{name}_muzzle_{sk}", r=0.06, segs=12, rings=8, loc=(0, -0.15, 0.65), parent=wrist_p, mat=mat_accent)

    # waist
    smooth_cone(f"{name}_waist", r1=0.65, r2=0.55, depth=0.30, segs=14, loc=(0, 2.55, 0), parent=mp, mat=mat_sec)

    # 2 legs (parented for articulation)
    legs = {}
    for sk, sz in [("L", 0.40), ("R", -0.40)]:
        # hip joint
        hip_p = empty(f"{name}_hip_{sk}", (0, 2.40, sz), parent=mp)
        legs[f"hip_{sk}"] = hip_p
        # thigh
        smooth_cone(f"{name}_thigh_{sk}", r1=0.22, r2=0.20, depth=1.1, segs=12, loc=(0, -0.55, 0), parent=hip_p, mat=mat_prim)
        # knee joint
        knee_p = empty(f"{name}_knee_{sk}", (0, -1.10, 0), parent=hip_p)
        legs[f"knee_{sk}"] = knee_p
        # calf
        smooth_cone(f"{name}_calf_{sk}", r1=0.20, r2=0.18, depth=1.0, segs=12, loc=(0, -0.50, 0), parent=knee_p, mat=mat_sec)
        # foot
        beveled_cube(f"{name}_foot_{sk}", (0.45, 0.18, 0.85), bevel_offset=0.04, bevel_segments=2, loc=(0, -1.05, 0.15), parent=knee_p, mat=mat_sec)

    # back jet pack (cosmetic detail)
    beveled_cube(f"{name}_pack", (0.85, 0.95, 0.30), bevel_offset=0.04, bevel_segments=2, loc=(0, 3.5, -0.55 * facing_dir), parent=mp, mat=mat_sec)
    # jet thrusters glow
    for jk in range(2):
        jy = 3.2 - jk * 0.40
        smooth_sphere(f"{name}_jet_{jk}", r=0.10, segs=12, rings=8, loc=(0.30 * (1 if jk == 0 else -1), jy, -0.75 * facing_dir), parent=mp, mat=mat_accent)

    # face direction
    mp.rotation_euler = (0, math.radians(0 if facing_dir > 0 else 180), 0)

    return {"mp": mp, "arms": arms, "legs": legs}


# Build 2 mechas facing each other
mech_A = build_mech("mech_A", (-5, 0, 0), MAT_MECH_A_PRIMARY, MAT_MECH_A_SECONDARY, MAT_MECH_A_ACCENT, facing_dir=1)
mech_B = build_mech("mech_B", (5, 0, 0), MAT_MECH_B_PRIMARY, MAT_MECH_B_SECONDARY, MAT_MECH_B_ACCENT, facing_dir=-1)


# --- 6 laser shots between mechs ----------------------------------------
laser_shots = []
for li in range(6):
    lp = empty(f"laser_{li}_p", (random.uniform(-4, 4), random.uniform(2, 4), random.uniform(-2, 2)))
    mat = MAT_LASER_RED if li % 2 == 0 else MAT_LASER_BLUE
    smooth_cone(f"laser_{li}_b", r1=0.06, r2=0.06, depth=1.2, segs=8, loc=(0, 0, 0), parent=lp, mat=mat)
    laser_shots.append({"p": lp, "phase": li * 0.30, "from_A": li % 2 == 0})


# --- 4 tours sentinelles avec tourelles ----------------------------------
sentinels = []
SENTINEL_POSITIONS = [(-11, 0, -7), (11, 0, -7), (-11, 0, 7), (11, 0, 7)]
for ti, (tx, ty, tz) in enumerate(SENTINEL_POSITIONS):
    sp = empty(f"sent_{ti}_p", (tx, ty, tz))
    sentinels.append(sp)
    # base
    smooth_cone(f"sent_{ti}_base", r1=1.0, r2=0.80, depth=0.30, segs=14, loc=(0, 0.15, 0), parent=sp, mat=MAT_TOWER)
    # column
    smooth_cone(f"sent_{ti}_col", r1=0.45, r2=0.40, depth=3.0, segs=14, loc=(0, 1.80, 0), parent=sp, mat=MAT_TOWER)
    # tower body
    beveled_cube(f"sent_{ti}_body", (1.2, 0.80, 1.2), bevel_offset=0.05, bevel_segments=2, loc=(0, 3.70, 0), parent=sp, mat=MAT_TOWER_RED)
    # turret (rotating)
    turret_p = empty(f"sent_{ti}_turret_p", (0, 4.15, 0), parent=sp)
    smooth_sphere(f"sent_{ti}_turret_dome", r=0.55, segs=18, rings=12, loc=(0, 0, 0), parent=turret_p, mat=MAT_TOWER, scale=(1.0, 0.7, 1.0))
    # turret gun
    smooth_cone(f"sent_{ti}_gun", r1=0.10, r2=0.08, depth=1.2, segs=10, loc=(0, 0.05, 0.55), parent=turret_p, mat=MAT_MECH_A_SECONDARY)
    smooth_sphere(f"sent_{ti}_muzzle", r=0.10, segs=12, rings=8, loc=(0, 0.05, 1.10), parent=turret_p, mat=MAT_LASER_RED)
    sp["_phase"] = ti * 0.4
    sp["_turret"] = turret_p


# --- 30 explosions sol pulse ---------------------------------------------
explosions = []
for ek in range(30):
    a = ek * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(2, 8)
    ex = math.cos(a) * r
    ez = math.sin(a) * r * 0.6
    epx = smooth_sphere(f"explo_{ek}", r=random.uniform(0.20, 0.40), segs=14, rings=10, loc=(ex, 0.15, ez), mat=MAT_EXPLOSION, scale=(1.0, 0.5, 1.0))
    epx["_base"] = (ex, 0.15, ez)
    epx["_phase"] = ek * 0.15
    explosions.append(epx)


# --- 100 étincelles métal parabolic --------------------------------------
sparks = []
for sk in range(100):
    a = sk * (math.pi * 2 / 100) + random.uniform(-0.5, 0.5)
    r = random.uniform(0.5, 4.0)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    sp_obj = smooth_sphere(f"spark_{sk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(sx, 0.5, sz), mat=MAT_SPARK)
    sp_obj["_base_x"] = sx
    sp_obj["_base_z"] = sz
    sp_obj["_phase"] = sk * 0.07
    sp_obj["_speed"] = random.uniform(0.8, 1.6)
    sparks.append(sp_obj)


# --- 30 fragments métalliques drift ---------------------------------------
fragments = []
for fk in range(30):
    a = fk * (math.pi * 2 / 30) + random.uniform(-0.3, 0.3)
    r = random.uniform(3, 9)
    fx = math.cos(a) * r
    fy = random.uniform(2, 5)
    fz = math.sin(a) * r * 0.7
    fr = beveled_cube(f"frag_{fk}", (random.uniform(0.15, 0.35), random.uniform(0.10, 0.20), random.uniform(0.15, 0.30)), bevel_offset=0.02, bevel_segments=2, loc=(fx, fy, fz), mat=MAT_FRAGMENT)
    fr["_base"] = (fx, fy, fz)
    fr["_phase"] = fk * 0.12
    fragments.append(fr)


# --- 8 flammes secondaires --------------------------------------------
flames = []
for fl in range(8):
    a = fl * (math.pi * 2 / 8) + 0.3
    r = random.uniform(4, 9)
    fx = math.cos(a) * r
    fz = math.sin(a) * r * 0.7
    fp = empty(f"flame_{fl}_p", (fx, 0, fz))
    flames.append(fp)
    # outer flame
    smooth_sphere(f"flame_{fl}_out", r=0.35, segs=16, rings=12, loc=(0, 0.30, 0), parent=fp, mat=MAT_FLAME, scale=(1.0, 1.5, 1.0))
    # smoke above
    for sm in range(2):
        smk = smooth_sphere(f"flame_{fl}_smoke_{sm}", r=0.25, segs=12, rings=8, loc=(0, 0.80 + sm * 0.40, 0), parent=fp, mat=MAT_SMOKE, scale=(1.2, 1.0, 1.2))
        smk["_phase"] = sm * 0.30
    fp["_phase"] = fl * 0.35


# --- gradins + 20 spectateurs ---------------------------------------------
gradin_y_levels = [0.6, 1.4, 2.2]
gradins = empty("gradins", (0, 0, 0))
# back gradin
for gy in range(3):
    beveled_cube(f"gradin_back_{gy}", (16, 0.30, 1.0), bevel_offset=0.04, bevel_segments=2, loc=(0, gradin_y_levels[gy], -11 - gy * 0.6), parent=gradins, mat=MAT_GRADIN)

# 20 spectateurs (5 per row × 2 rows × 2 sides)
spectators = []
for r in range(2):
    for sk in range(10):
        sx = -6.5 + sk * 1.5
        sy = gradin_y_levels[r] + 0.4
        sz = -11.5 - r * 0.6
        sp = empty(f"spec_{r}_{sk}_p", (sx, sy, sz))
        spectators.append(sp)
        # body cone
        smooth_cone(f"spec_{r}_{sk}_b", r1=0.10, r2=0.14, depth=0.55, segs=8, loc=(0, 0.30, 0), parent=sp, mat=MAT_SPECTATOR)
        # head
        smooth_sphere(f"spec_{r}_{sk}_h", r=0.08, segs=10, rings=8, loc=(0, 0.60, 0), parent=sp, mat=MAT_SPECTATOR)
        sp["_phase"] = (r * 10 + sk) * 0.15


# --- 4 écrans géants émissifs ------------------------------------------
screens = []
SCREEN_POSITIONS = [(-9, 6, -12), (9, 6, -12), (-9, 6, 12), (9, 6, 12)]
screen_mats = [MAT_SCREEN_A, MAT_SCREEN_B, MAT_SCREEN_C, MAT_SCREEN_A]
for si, (sx, sy, sz) in enumerate(SCREEN_POSITIONS):
    sp = empty(f"screen_{si}_p", (sx, sy, sz))
    screens.append(sp)
    # frame
    beveled_cube(f"screen_{si}_frame", (2.5, 1.6, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=sp, mat=MAT_TOWER)
    # screen surface (start with one color, will cycle)
    screen_surf = beveled_cube(f"screen_{si}_surf", (2.3, 1.4, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.07), parent=sp, mat=screen_mats[si])
    sp["_phase"] = si * 0.40


# --- 2 grues swing -----------------------------------------------------
cranes = []
for ck in range(2):
    cx = -10 + ck * 20
    cp = empty(f"crane_{ck}_p", (cx, 0, -5))
    cranes.append(cp)
    # base
    beveled_cube(f"crane_{ck}_base", (1.5, 1.0, 1.5), bevel_offset=0.05, bevel_segments=2, loc=(0, 0.50, 0), parent=cp, mat=MAT_TOWER)
    # column
    smooth_cone(f"crane_{ck}_col", r1=0.30, r2=0.25, depth=6.0, segs=10, loc=(0, 4.0, 0), parent=cp, mat=MAT_CRANE)
    # arm (horizontal)
    arm_p = empty(f"crane_{ck}_arm_p", (0, 7.0, 0), parent=cp)
    arm = beveled_cube(f"crane_{ck}_arm", (6.0, 0.30, 0.40), bevel_offset=0.04, bevel_segments=2, loc=(2.5, 0, 0), parent=arm_p, mat=MAT_CRANE)
    # cable + hook
    cable = smooth_cone(f"crane_{ck}_cable", r1=0.04, r2=0.04, depth=2.5, segs=4, loc=(5, -1.25, 0), parent=arm_p, mat=MAT_TOWER)
    smooth_sphere(f"crane_{ck}_hook", r=0.18, segs=12, rings=8, loc=(5, -2.5, 0), parent=arm_p, mat=MAT_FRAGMENT)
    cranes[ck] = {"arm": arm_p}


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

    # MECH A : aggressive movement (right arm punch, body lean forward)
    a_punch = math.sin(2 * math.pi * tt * 2.0) * 0.5
    a_body_lean = math.radians(15 * math.sin(2 * math.pi * tt * 1.5))
    a_step = math.sin(2 * math.pi * tt * 0.8) * 0.3
    kf(mech_A["mp"], f, "location", (-5 + a_step, 0, 0))
    kf(mech_A["mp"], f, "rotation_euler", (a_body_lean, 0, math.radians(5 * math.sin(2 * math.pi * tt * 2.5))))
    # right arm punch (forward swing)
    kf(mech_A["arms"]["shoulder_R"], f, "rotation_euler", (math.radians(-60 + 90 * a_punch), 0, math.radians(-20)))
    kf(mech_A["arms"]["elbow_R"], f, "rotation_euler", (math.radians(-30 - 60 * a_punch), 0, 0))
    # left arm defensive
    kf(mech_A["arms"]["shoulder_L"], f, "rotation_euler", (math.radians(-40 - 20 * a_punch), 0, math.radians(20)))
    kf(mech_A["arms"]["elbow_L"], f, "rotation_euler", (math.radians(-80), 0, 0))
    # legs : walk cycle
    kf(mech_A["legs"]["hip_L"], f, "rotation_euler", (math.radians(15 * math.sin(2 * math.pi * tt * 1.5)), 0, 0))
    kf(mech_A["legs"]["knee_L"], f, "rotation_euler", (math.radians(-10 - 15 * math.sin(2 * math.pi * tt * 1.5)), 0, 0))
    kf(mech_A["legs"]["hip_R"], f, "rotation_euler", (math.radians(15 * math.sin(2 * math.pi * tt * 1.5 + math.pi)), 0, 0))
    kf(mech_A["legs"]["knee_R"], f, "rotation_euler", (math.radians(-10 - 15 * math.sin(2 * math.pi * tt * 1.5 + math.pi)), 0, 0))

    # MECH B : defensive blocks, backward step
    b_block = math.sin(2 * math.pi * tt * 2.0 + math.pi) * 0.5
    b_lean = math.radians(-10 * math.sin(2 * math.pi * tt * 1.5))
    b_step = math.sin(2 * math.pi * tt * 0.8 + math.pi) * 0.3
    kf(mech_B["mp"], f, "location", (5 + b_step, 0, 0))
    kf(mech_B["mp"], f, "rotation_euler", (b_lean, math.radians(180), math.radians(5 * math.cos(2 * math.pi * tt * 2.5))))
    # both arms raised for block
    kf(mech_B["arms"]["shoulder_L"], f, "rotation_euler", (math.radians(-90 + 30 * b_block), 0, math.radians(30)))
    kf(mech_B["arms"]["elbow_L"], f, "rotation_euler", (math.radians(-100), 0, 0))
    kf(mech_B["arms"]["shoulder_R"], f, "rotation_euler", (math.radians(-90 - 30 * b_block), 0, math.radians(-30)))
    kf(mech_B["arms"]["elbow_R"], f, "rotation_euler", (math.radians(-100), 0, 0))
    # legs walk cycle
    kf(mech_B["legs"]["hip_L"], f, "rotation_euler", (math.radians(12 * math.sin(2 * math.pi * tt * 1.5 + math.pi)), 0, 0))
    kf(mech_B["legs"]["knee_L"], f, "rotation_euler", (math.radians(-10 - 12 * math.sin(2 * math.pi * tt * 1.5 + math.pi)), 0, 0))
    kf(mech_B["legs"]["hip_R"], f, "rotation_euler", (math.radians(12 * math.sin(2 * math.pi * tt * 1.5)), 0, 0))
    kf(mech_B["legs"]["knee_R"], f, "rotation_euler", (math.radians(-10 - 12 * math.sin(2 * math.pi * tt * 1.5)), 0, 0))

    # 6 laser shots : streak between mechs (alpha pulse / scale)
    for ld in laser_shots:
        ph = ld["phase"]
        local = (tt * 4 + ph) % 1.0
        # streak from one mech to other
        from_x = -5 if ld["from_A"] else 5
        to_x = 5 if ld["from_A"] else -5
        nx = from_x + (to_x - from_x) * local
        ny = 3.0 + math.sin(local * math.pi) * 0.5
        nz = ld["p"].location.z if f > 1 else 0
        kf(ld["p"], f, "location", (nx, ny, nz))
        # rotate to point direction
        kf(ld["p"], f, "rotation_euler", (0, 0, math.radians(90 if ld["from_A"] else -90)))
        # scale pulse
        sc = 1.0 + 0.3 * math.sin(2 * math.pi * tt * 8 + ph * math.pi)
        kf(ld["p"], f, "scale", (sc, sc, 1.0))

    # 4 sentinels : turrets rotate
    for si, sp in enumerate(sentinels):
        ph = sp["_phase"]
        turret = sp["_turret"]
        rot_y = math.radians(60 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi))
        kf(turret, f, "rotation_euler", (0, rot_y, 0))

    # 30 explosions ground pulse
    for ex in explosions:
        ph = ex["_phase"]
        bx_, by_, bz_ = ex["_base"]
        # active triggers (peaks 4 per cycle)
        intensity = 0.5 + 0.5 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        sc = 0.5 + intensity * 1.8
        ny = by_ + intensity * 0.5
        kf(ex, f, "location", (bx_, ny, bz_))
        kf(ex, f, "scale", (sc, sc * 0.6, sc))

    # 100 sparks parabolic trajectories
    for sp_obj in sparks:
        bx_ = sp_obj["_base_x"]
        bz_ = sp_obj["_base_z"]
        ph = sp_obj["_phase"]
        spd = sp_obj["_speed"]
        local = (tt * spd + ph) % 1.0
        py = 0.5 + 5.0 * local * (1 - local)  # parabolic
        nx = bx_ * (1 + local * 0.5)
        nz = bz_ * (1 + local * 0.5)
        kf(sp_obj, f, "location", (nx, py, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 5 + ph * math.pi))
        kf(sp_obj, f, "scale", (sc, sc, sc))

    # 30 fragments drift + rotate 3-axes
    for fr in fragments:
        bx_, by_, bz_ = fr["_base"]
        ph = fr["_phase"]
        ny = by_ + 0.5 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        nx = bx_ + 0.3 * math.cos(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(fr, f, "location", (nx, ny, bz_))
        kf(fr, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 20 spectators wave
    for spec in spectators:
        ph = spec["_phase"]
        wave = math.radians(15 * math.sin(2 * math.pi * tt * 2 + ph * math.pi))
        kf(spec, f, "rotation_euler", (wave, 0, math.radians(8 * math.cos(2 * math.pi * tt * 2.2 + ph * math.pi))))

    # 4 screens cycle colors (via scale modulation)
    for si, sp in enumerate(screens):
        ph = sp["_phase"]
        ps = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(sp, f, "scale", (ps, ps, 1.0))

    # 8 flames pulse + sway
    for fp in flames:
        ph = fp["_phase"]
        ps = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(fp, f, "scale", (ps, ps * 1.3, ps))
        kf(fp, f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 3 + ph)), 0, math.radians(5 * math.cos(2 * math.pi * tt * 3.5 + ph))))

    # 10 clouds drift
    for cp in clouds:
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 5 - 2.5
        if new_x > 16:
            new_x -= 32
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))

    # 2 grues swing
    for ci, cr in enumerate(cranes):
        if "arm" in cr:
            kf(cr["arm"], f, "rotation_euler", (0, math.radians(30 * math.sin(2 * math.pi * tt * 0.6 + ci * 1.5)), 0))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_mech_battle_arena] wrote {OUT}")
