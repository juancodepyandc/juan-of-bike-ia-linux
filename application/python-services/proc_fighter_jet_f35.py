"""
proc_fighter_jet_f35.py — 140e procédural AuroraIA, MILESTONE 140 — Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axis anim).

Avion de chasse F-35 furtif :
- fuselage profilé bevelé smooth
- cockpit bulle transparent
- 2 ailes delta angled
- 2 stabilisateurs verticaux + 2 horizontaux
- 2 turbo-jets émissifs arrière
- 6 missiles air-air sous ailes
- nez radar pointu
- pilote silhouette dans cockpit
- 4 trains d'atterrissage rétractables
- drapeau US sur queue
- cockpit instruments (HUD)
- ciel haute altitude + 3 nuages

Animations multi-axes simultanées :
- jet : vol courbe (translate XY + rotate banking)
- 2 ailerons : pitch ±10° différentiel
- 2 turboréacteurs : émission pulse intense + scale
- 6 missiles : prêts (pas anim mais visibles)
- pilote : head bob léger
- 4 trains : deploys + retracts cycliquement
- drapeau : wave
- HUD : pulse cyan

Sortie : output/3d/pbr_fighterjet_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_fighterjet_proc.glb"))

random.seed(0xCAFE40)

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
    bmesh.ops.bevel(
        bm,
        geom=bm.edges[:] + bm.verts[:],
        offset=bevel_offset,
        segments=bevel_segments,
        profile=0.5,
        affect='EDGES',
    )
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
MAT_SKY_HIGH = make_mat("sky_high", (0.30, 0.55, 0.92), roughness=1.0,
                          emi=(0.20, 0.45, 0.85), emi_strength=0.5)
MAT_CLOUD = make_mat("cloud", (0.98, 0.98, 1.0), roughness=1.0, alpha=0.92,
                       emi=(0.90, 0.92, 0.98), emi_strength=0.4)
MAT_FIGHTER_GREY = make_mat("fighter_grey", (0.35, 0.38, 0.42), metallic=0.85, roughness=0.30,
                              emi=(0.08, 0.10, 0.12), emi_strength=0.20)
MAT_FIGHTER_DARK = make_mat("fighter_dark", (0.15, 0.16, 0.20), metallic=0.80, roughness=0.40)
MAT_FIGHTER_STEALTH = make_mat("fighter_stealth", (0.10, 0.12, 0.15), metallic=0.70, roughness=0.50)
MAT_COCKPIT_GLASS = make_mat("cockpit_glass", (0.10, 0.18, 0.28), roughness=0.0, alpha=0.45, metallic=0.55,
                               emi=(0.10, 0.15, 0.25), emi_strength=0.45)
MAT_COCKPIT_FRAME = make_mat("cockpit_frame", (0.20, 0.20, 0.25), metallic=0.70, roughness=0.30)
MAT_NOSE = make_mat("nose", (0.08, 0.08, 0.10), metallic=0.60, roughness=0.40)
MAT_TURBO = make_mat("turbo", (0.40, 0.40, 0.45), metallic=0.95, roughness=0.15,
                       emi=(0.10, 0.10, 0.12), emi_strength=0.30)
MAT_AFTERBURNER = make_mat("afterburner", (1.0, 0.50, 0.10), roughness=0.0, alpha=0.85,
                             emi=(1.0, 0.50, 0.10), emi_strength=15.0)
MAT_AFTERBURNER_CORE = make_mat("afterburner_core", (1.0, 0.85, 0.30), roughness=0.0,
                                  emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_MISSILE = make_mat("missile", (0.70, 0.70, 0.72), metallic=0.85, roughness=0.25)
MAT_MISSILE_TIP = make_mat("missile_tip", (0.85, 0.15, 0.10), metallic=0.5, roughness=0.30,
                             emi=(0.35, 0.05, 0.05), emi_strength=0.5)
MAT_LANDING_GEAR = make_mat("gear", (0.30, 0.30, 0.32), metallic=0.80, roughness=0.30)
MAT_LANDING_WHEEL = make_mat("gear_wheel", (0.05, 0.05, 0.05), roughness=0.85)
MAT_PILOT_HELMET = make_mat("pilot_helmet", (0.10, 0.10, 0.10), roughness=0.40,
                              emi=(0.05, 0.05, 0.05), emi_strength=0.2)
MAT_PILOT_VISOR = make_mat("pilot_visor", (1.0, 0.78, 0.20), metallic=0.90, roughness=0.20,
                             emi=(0.40, 0.30, 0.05), emi_strength=0.50)
MAT_PILOT_SUIT = make_mat("pilot_suit", (0.18, 0.30, 0.20), roughness=0.6)
MAT_HUD_DISPLAY = make_mat("hud", (0.20, 1.0, 0.60), roughness=0.0, alpha=0.55,
                             emi=(0.20, 1.0, 0.50), emi_strength=6.0)
MAT_FLAG_RED = make_mat("flag_red", (0.85, 0.10, 0.10), roughness=0.6,
                          emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_FLAG_WHITE = make_mat("flag_white", (0.95, 0.95, 0.95), roughness=0.6,
                            emi=(0.40, 0.40, 0.42), emi_strength=0.3)
MAT_FLAG_BLUE = make_mat("flag_blue", (0.10, 0.20, 0.50), roughness=0.6,
                           emi=(0.05, 0.10, 0.25), emi_strength=0.3)
MAT_NAV_LIGHT_R = make_mat("nav_red", (1.0, 0.10, 0.10), roughness=0.0,
                             emi=(1.0, 0.10, 0.10), emi_strength=10.0)
MAT_NAV_LIGHT_G = make_mat("nav_green", (0.10, 1.0, 0.30), roughness=0.0,
                             emi=(0.10, 1.0, 0.30), emi_strength=10.0)
MAT_NAV_LIGHT_W = make_mat("nav_white", (1.0, 1.0, 0.95), roughness=0.0,
                             emi=(1.0, 1.0, 0.95), emi_strength=12.0)

# --- backdrop : high altitude sky ----------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 6), mat=MAT_SKY_HIGH)

# 3 clouds at altitude
for i, (cx, cy, cz) in enumerate([(-8, 12, 4), (6, 13, -2), (10, 11, 5)]):
    cl = smooth_sphere(f"cloud_{i}", r=random.uniform(1.5, 2.2), segs=22, rings=14, loc=(cx, cy, cz), mat=MAT_CLOUD, scale=(1.6, 0.55, 1.2))

# --- F-35 fighter jet ------------------------------------------------------
fighter = empty("fighter", (0, 5.0, 0))

# fuselage main (long sphere stretched + bevelled)
def make_fuselage(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.6)
    bmesh.ops.scale(bm, vec=(4.0, 1.0, 1.1), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0, 0)
    me.materials.append(MAT_FIGHTER_GREY)
    smooth_shade(me)
    return o

fuselage = make_fuselage("fuselage", fighter)

# nose radar (pointed cone)
nose = smooth_cone("nose", r1=0.55, r2=0.05, depth=1.2, segs=24, loc=(3.0, 0, 0), parent=fighter, mat=MAT_NOSE)
nose.rotation_euler = (0, math.radians(90), 0)

# 2 air intakes (sphères squashed sur les côtés)
for side, dz in [("L", 0.65), ("R", -0.65)]:
    intake = smooth_sphere(f"intake_{side}", r=0.30, segs=20, rings=14, loc=(0.5, -0.15, dz), parent=fighter, mat=MAT_FIGHTER_DARK, scale=(1.5, 0.7, 1.0))
    # inner opening (darker)
    opening = smooth_cone(f"intake_{side}_op", r1=0.18, r2=0.20, depth=0.15, segs=18, loc=(1.0, -0.15, dz), parent=fighter, mat=MAT_FIGHTER_STEALTH)
    opening.rotation_euler = (0, math.radians(90), 0)

# cockpit bubble (transparent glass)
cockpit_glass = smooth_sphere("cockpit_glass", r=0.45, segs=24, rings=18, loc=(1.2, 0.45, 0), parent=fighter, mat=MAT_COCKPIT_GLASS, scale=(1.6, 0.7, 0.85))
# cockpit frame (around opening base)
cockpit_frame = smooth_cone("cockpit_frame", r1=0.50, r2=0.45, depth=0.06, segs=22, loc=(1.2, 0.25, 0), parent=fighter, mat=MAT_COCKPIT_FRAME)
cockpit_frame.rotation_euler = (math.radians(90), 0, 0)
cockpit_frame.scale = (1.6, 1.0, 0.85)

# --- pilot inside cockpit -----------------------------------------------
pilot_p = empty("pilot_p", (1.1, 0.35, 0), parent=fighter)
# torso
pilot_torso = beveled_cube("pilot_torso", (0.25, 0.30, 0.30), bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=pilot_p, mat=MAT_PILOT_SUIT)
# helmet (sphere)
pilot_helmet = smooth_sphere("pilot_helmet", r=0.18, segs=20, rings=14, loc=(0, 0.30, 0), parent=pilot_p, mat=MAT_PILOT_HELMET)
# visor (gold)
pilot_visor = smooth_sphere("pilot_visor", r=0.16, segs=18, rings=12, loc=(0.06, 0.30, 0), parent=pilot_p, mat=MAT_PILOT_VISOR)
pilot_visor.scale = (0.4, 0.6, 1.0)

# HUD display (small green glowing rectangle in front of pilot)
hud = beveled_cube("hud", (0.04, 0.18, 0.30), bevel_offset=0.02, bevel_segments=2, loc=(1.55, 0.30, 0), parent=fighter, mat=MAT_HUD_DISPLAY)

# --- 2 wings delta angled -----------------------------------------------
def make_wing(name, x_off, z_dir, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    # create a flat wedge (4-sided pyramid)
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(1.6, 0.08, 1.8), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=0.08, segments=3, profile=0.5, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (x_off, -0.05, z_dir * 1.7)
    me.materials.append(MAT_FIGHTER_GREY)
    smooth_shade(me)
    # angle sweep (delta)
    o.rotation_euler = (0, z_dir * math.radians(25), 0)
    return o

wing_L = make_wing("wing_L", 0, 1, fighter)
wing_R = make_wing("wing_R", 0, -1, fighter)

# --- 6 missiles air-air (sous ailes) ----------------------------------
missile_data = [
    (wing_L, [(-0.5, -0.30, 0), (0, -0.30, 0.4), (0.5, -0.30, 0)]),
    (wing_R, [(-0.5, -0.30, 0), (0, -0.30, -0.4), (0.5, -0.30, 0)]),
]
for wing, locs in missile_data:
    for k, (mx, my, mz) in enumerate(locs):
        # missile body
        m = smooth_cone(f"missile_{wing.name}_{k}", r1=0.06, r2=0.06, depth=0.7, segs=14, loc=(mx, my, mz), parent=wing, mat=MAT_MISSILE)
        m.rotation_euler = (0, math.radians(90), 0)
        # missile nose (red)
        tip = smooth_cone(f"missile_{wing.name}_{k}_tip", r1=0.06, r2=0.0, depth=0.15, segs=12, loc=(mx + 0.42, my, mz), parent=wing, mat=MAT_MISSILE_TIP)
        tip.rotation_euler = (0, math.radians(90), 0)
        # 4 fins
        for fk in range(4):
            fa = fk * (math.pi / 2)
            fin = beveled_cube(f"missile_{wing.name}_{k}_fin_{fk}", (0.10, 0.04, 0.06), bevel_offset=0.01, bevel_segments=2, loc=(mx - 0.30, my + math.sin(fa) * 0.08, mz + math.cos(fa) * 0.08), parent=wing, mat=MAT_MISSILE)
            fin.rotation_euler = (fa, 0, 0)

# --- 2 stabilisateurs verticaux (V-tail style) -----------------------
for side, dz, rot in [("L", 0.45, math.radians(20)), ("R", -0.45, math.radians(-20))]:
    me = bpy.data.meshes.new(f"stabilizer_{side}")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.50, 0.85, 0.08), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=0.05, segments=3, profile=0.5, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    stab = add_obj(f"stabilizer_{side}", me, fighter)
    stab.location = (-1.8, 0.4, dz)
    me.materials.append(MAT_FIGHTER_GREY)
    smooth_shade(me)
    stab.rotation_euler = (0, 0, rot)
    # nav light at top
    light_mat = MAT_NAV_LIGHT_R if side == "L" else MAT_NAV_LIGHT_G
    nav = smooth_sphere(f"nav_{side}", r=0.06, segs=14, rings=10, loc=(-1.8, 0.85, dz + 0.25 * (1 if side == "L" else -1)), parent=fighter, mat=light_mat)

# --- 2 stabilisateurs horizontaux (canards arrière) ------------------
ailerons = []
for side, dz in [("L", 0.85), ("R", -0.85)]:
    ail_p = empty(f"aileron_p_{side}", (-1.85, -0.05, dz), parent=fighter)
    me = bpy.data.meshes.new(f"aileron_{side}")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.50, 0.06, 0.45), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=0.05, segments=3, profile=0.5, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    ail = add_obj(f"aileron_{side}", me, ail_p)
    ail.location = (0, 0, 0)
    me.materials.append(MAT_FIGHTER_GREY)
    smooth_shade(me)
    ailerons.append(ail_p)

# --- 2 turboréacteurs arrière -----------------------------------------
turbos = []
afterburners = []
for side, dz in [("L", 0.32), ("R", -0.32)]:
    # turbo body (cylinder)
    turbo = smooth_cone(f"turbo_{side}", r1=0.35, r2=0.32, depth=0.50, segs=24, loc=(-2.0, 0, dz), parent=fighter, mat=MAT_TURBO)
    turbo.rotation_euler = (0, math.radians(90), 0)
    turbos.append(turbo)
    # afterburner ring (annular emissive)
    ab_ring = smooth_cone(f"afterburner_ring_{side}", r1=0.30, r2=0.30, depth=0.05, segs=22, loc=(-2.30, 0, dz), parent=fighter, mat=MAT_AFTERBURNER)
    ab_ring.rotation_euler = (0, math.radians(90), 0)
    # afterburner core (sphere stretched flame)
    ab_core = smooth_sphere(f"afterburner_core_{side}", r=0.30, segs=20, rings=14, loc=(-2.50, 0, dz), parent=fighter, mat=MAT_AFTERBURNER_CORE, scale=(2.0, 0.85, 0.85))
    afterburners.append((ab_ring, ab_core))

# --- 4 trains d'atterrissage rétractables -----------------------------
landing_gears = []
gear_data = [
    (1.5, -0.50, 0),   # nose
    (-0.5, -0.50, 0.7), # main L
    (-0.5, -0.50, -0.7), # main R
    (-1.3, -0.50, 0),   # tail support
]
for i, (gx, gy, gz) in enumerate(gear_data):
    gear_p = empty(f"gear_p_{i}", (gx, gy, gz), parent=fighter)
    # strut
    strut = smooth_cone(f"gear_{i}_strut", r1=0.03, r2=0.03, depth=0.45, segs=10, loc=(0, -0.225, 0), parent=gear_p, mat=MAT_LANDING_GEAR)
    # wheel
    wheel = smooth_cone(f"gear_{i}_wheel", r1=0.10, r2=0.10, depth=0.08, segs=18, loc=(0, -0.50, 0), parent=gear_p, mat=MAT_LANDING_WHEEL)
    wheel.rotation_euler = (0, math.radians(90), 0)
    # rim
    rim = smooth_cone(f"gear_{i}_rim", r1=0.05, r2=0.05, depth=0.09, segs=14, loc=(0, -0.50, 0), parent=gear_p, mat=MAT_LANDING_GEAR)
    rim.rotation_euler = (0, math.radians(90), 0)
    landing_gears.append(gear_p)

# --- drapeau US (5 stripes + canton on tail) -------------------------
# Place flag on tail fuselage section
for k in range(5):
    ky = 0.20 + k * 0.06
    mat = MAT_FLAG_RED if k % 2 == 0 else MAT_FLAG_WHITE
    stripe = beveled_cube(f"flag_stripe_{k}", (0.08, 0.06, 0.35), bevel_offset=0.01, bevel_segments=2, loc=(-1.50, ky, 0.55), parent=fighter, mat=mat)
# blue canton (top-left)
canton = beveled_cube("flag_canton", (0.08, 0.10, 0.18), bevel_offset=0.01, bevel_segments=2, loc=(-1.50, 0.40, 0.45), parent=fighter, mat=MAT_FLAG_BLUE)

# --- nav lights (white on nose, taillight white at tail) ---------------
nose_light = smooth_sphere("nose_light", r=0.05, segs=12, rings=8, loc=(3.55, 0, 0), parent=fighter, mat=MAT_NAV_LIGHT_W)
tail_light = smooth_sphere("tail_light", r=0.06, segs=12, rings=8, loc=(-2.10, 0.55, 0), parent=fighter, mat=MAT_NAV_LIGHT_W)

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

# fighter : circular flight path with banking + altitude variation
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 2.0
    cx = math.cos(angle) * 6.0
    cz = math.sin(angle) * 4.0
    cy = 5.0 + math.sin(tt * math.pi * 3.0) * 0.5
    kf_loc(fighter, f, (cx, cy, cz))
    # banking based on turn rate
    bank = math.radians(20) * math.sin(angle * 1.0)
    # heading aligned with motion
    heading = -angle + math.pi / 2
    pitch = math.radians(5) * math.cos(tt * math.pi * 3.0)
    kf_rot(fighter, f, (pitch, heading, bank))

# 2 ailerons pitch ±10° différentiel
for i, ail in enumerate(ailerons):
    sign = 1 if i == 0 else -1
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        angle = math.radians(15) * math.sin(tt * math.pi * 4.0) * sign
        kf_rot(ail, f, (angle, 0, 0))

# 2 afterburners pulse intense
for i, (ring, core) in enumerate(afterburners):
    phase = i * 0.2
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s_ring = 1.0 + 0.30 * math.sin(tt * math.pi * 10.0 + phase)
        kf_scale(ring, f, (s_ring, s_ring, s_ring))
        s_core = 1.0 + 0.40 * math.sin(tt * math.pi * 12.0 + phase)
        kf_scale(core, f, (2.0 * s_core, 0.85 * s_core, 0.85 * s_core))

# 4 landing gears retract/deploy cycliquement
for i, gear_p in enumerate(landing_gears):
    phase = i * 0.3
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        # cycle : deployed → retracted → deployed every half-loop
        local = (tt * 2.0 + phase) % 1.0
        if local < 0.5:
            # retract (rotate up)
            angle = local * 2.0 * math.radians(90)
        else:
            # deploy (rotate down)
            angle = (1.0 - local) * 2.0 * math.radians(90)
        kf_rot(gear_p, f, (angle, 0, 0))

# pilot head subtle bob
pilot_helmet_obj = bpy.data.objects.get("pilot_helmet")
if pilot_helmet_obj:
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bob = math.radians(5) * math.sin(tt * math.pi * 5.0)
        kf_rot(pilot_helmet_obj, f, (bob, 0, 0))

# HUD pulse
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.10 * math.sin(tt * math.pi * 8.0)
    kf_scale(hud, f, (s, s, s))

# nose + tail lights pulse fast
for light_obj in [nose_light, tail_light]:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 15.0)
        kf_scale(light_obj, f, (s, s, s))

# clouds drift slow
for i in range(3):
    cl = bpy.data.objects.get(f"cloud_{i}")
    if cl:
        base_x = cl.location.x
        base_z = cl.location.z
        for f in range(1, FRAMES + 1, 5):
            tt = (f - 1) / (FRAMES - 1)
            dx = base_x + 0.4 * math.sin(tt * math.pi * 1.5 + i * 0.6)
            dz = base_z + 0.3 * math.cos(tt * math.pi * 1.2 + i * 0.4)
            kf_loc(cl, f, (dx, cl.location.y, dz))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_fighterjet] wrote {OUT}")
