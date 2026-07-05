"""
proc_helicopter_apache.py — 146e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Hélicoptère AH-64 Apache militaire smooth shaded :
- fuselage profilé bevelé (cockpit tandem)
- 2 cockpits avec 2 pilotes silhouettes + 2 windshield slanted
- main rotor 4 lames (spins ultra fast)
- tail boom + tail rotor 4 lames
- 4 landing skids
- 2 stub wings avec 4 hardpoints chacun = 8 hardpoints total
- 6 missiles Hellfire (3 par côté) + 2 rocket pods (19 tubes each)
- chain gun rotatif M230 sous nez
- canopée vitrée + cockpit instruments
- 2 sensors FLIR
- 2 turbojets émissifs avec exhaust
- drapeau US arrière
- ciel battlefield
- 4 nuages
- montagnes background

Animations multi-axes simultanées :
- main rotor : rotate Y 60π·t (30 turns/loop ULTRA FAST)
- tail rotor : rotate X 80π·t
- helicopter : circular flight path + banking + altitude variation
- chain gun : rotate sweep ±30°
- 2 sensors : pivot
- 2 pilots head bob
- turbojets : pulse intense

Sortie : output/3d/pbr_apache_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_apache_proc.glb"))

random.seed(0xCAFEA1)

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
MAT_SKY = make_mat("sky", (0.50, 0.55, 0.65), roughness=1.0,
                    emi=(0.35, 0.40, 0.50), emi_strength=0.4)
MAT_CLOUD = make_mat("cloud", (0.95, 0.95, 1.0), roughness=1.0, alpha=0.85,
                       emi=(0.80, 0.85, 0.92), emi_strength=0.3)
MAT_MOUNTAIN = make_mat("mountain", (0.30, 0.32, 0.35), roughness=0.95)
MAT_FUSELAGE = make_mat("fuselage", (0.30, 0.35, 0.28), metallic=0.75, roughness=0.40,
                          emi=(0.08, 0.10, 0.07), emi_strength=0.20)
MAT_FUSELAGE_DARK = make_mat("fuselage_dark", (0.10, 0.12, 0.10), metallic=0.70, roughness=0.45)
MAT_CANOPY = make_mat("canopy", (0.08, 0.12, 0.18), roughness=0.0, alpha=0.40, metallic=0.60,
                        emi=(0.05, 0.10, 0.18), emi_strength=0.50)
MAT_ROTOR_BLADE = make_mat("rotor_blade", (0.08, 0.08, 0.10), metallic=0.75, roughness=0.35)
MAT_ROTOR_HUB = make_mat("rotor_hub", (0.20, 0.20, 0.22), metallic=0.85, roughness=0.25)
MAT_SKID = make_mat("skid", (0.40, 0.40, 0.42), metallic=0.85, roughness=0.30)
MAT_PILOT_HELMET = make_mat("helmet", (0.10, 0.10, 0.10), roughness=0.40,
                              emi=(0.05, 0.05, 0.05), emi_strength=0.2)
MAT_PILOT_VISOR = make_mat("visor", (0.10, 0.15, 0.10), metallic=0.80, roughness=0.20,
                             emi=(0.05, 0.15, 0.05), emi_strength=0.40)
MAT_PILOT_SUIT = make_mat("suit", (0.20, 0.25, 0.18), roughness=0.6)
MAT_MISSILE = make_mat("missile", (0.50, 0.50, 0.55), metallic=0.80, roughness=0.30)
MAT_MISSILE_TIP = make_mat("missile_tip", (0.85, 0.15, 0.10), metallic=0.50, roughness=0.30,
                             emi=(0.30, 0.05, 0.05), emi_strength=0.5)
MAT_ROCKET_POD = make_mat("rocket_pod", (0.20, 0.22, 0.18), metallic=0.70, roughness=0.40)
MAT_ROCKET_TUBE = make_mat("rocket_tube", (0.05, 0.05, 0.05), roughness=0.50)
MAT_CHAIN_GUN = make_mat("chain_gun", (0.15, 0.15, 0.15), metallic=0.75, roughness=0.40)
MAT_SENSOR = make_mat("sensor", (0.15, 0.18, 0.15), metallic=0.75, roughness=0.30,
                        emi=(0.08, 0.10, 0.08), emi_strength=0.30)
MAT_FLIR_LENS = make_mat("flir_lens", (0.10, 0.55, 0.40), roughness=0.0,
                           emi=(0.10, 0.85, 0.50), emi_strength=6.0)
MAT_TURBOJET = make_mat("turbojet", (0.40, 0.40, 0.45), metallic=0.90, roughness=0.20,
                          emi=(0.10, 0.10, 0.12), emi_strength=0.30)
MAT_EXHAUST_HEAT = make_mat("exhaust", (1.0, 0.30, 0.05), roughness=0.0, alpha=0.85,
                              emi=(1.0, 0.30, 0.05), emi_strength=12.0)
MAT_NAV_RED = make_mat("nav_red", (1.0, 0.10, 0.10), roughness=0.0,
                         emi=(1.0, 0.10, 0.10), emi_strength=10.0)
MAT_NAV_GREEN = make_mat("nav_green", (0.10, 1.0, 0.30), roughness=0.0,
                           emi=(0.10, 1.0, 0.30), emi_strength=10.0)
MAT_NAV_WHITE = make_mat("nav_white", (1.0, 1.0, 0.95), roughness=0.0,
                           emi=(1.0, 1.0, 0.95), emi_strength=12.0)
MAT_FLAG_R = make_mat("flag_r", (0.85, 0.10, 0.10), roughness=0.6,
                        emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_FLAG_W = make_mat("flag_w", (0.95, 0.95, 0.95), roughness=0.6,
                        emi=(0.40, 0.40, 0.42), emi_strength=0.3)
MAT_FLAG_B = make_mat("flag_b", (0.10, 0.20, 0.50), roughness=0.6,
                        emi=(0.05, 0.10, 0.25), emi_strength=0.3)

# --- backdrop : battlefield sky ---------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 6), mat=MAT_SKY)

# 4 clouds
for i, (cx, cy, cz) in enumerate([(-12, 14, 7), (-3, 13, 8), (5, 14, 9), (11, 13.5, 6)]):
    cl = smooth_sphere(f"cloud_{i}", r=random.uniform(1.4, 2.0), segs=20, rings=14, loc=(cx, cy, cz), mat=MAT_CLOUD, scale=(1.7, 0.55, 1.1))

# 3 background mountains
for i, (mx, mh, mw) in enumerate([(-9, 4, 5), (9, 5, 5), (0, 3, 4)]):
    mp = empty(f"mount_{i}", (mx, 0, 11))
    m = smooth_cone(f"mount_{i}_body", r1=mw, r2=0.4, depth=mh, segs=14, loc=(0, mh / 2, 0), parent=mp, mat=MAT_MOUNTAIN)
    m.rotation_euler = (math.radians(90), 0, 0)
    # snow cap (small)
    cap = smooth_cone(f"mount_{i}_cap", r1=1.5, r2=0.1, depth=1.0, segs=10, loc=(0, mh - 0.5, 0), parent=mp, mat=MAT_FUSELAGE_DARK)
    cap.rotation_euler = (math.radians(90), 0, 0)

# --- Apache helicopter ------------------------------------------
apache = empty("apache", (0, 6, 0))

# Main fuselage (long, profilé)
def make_fuselage(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.55)
    bmesh.ops.scale(bm, vec=(2.8, 0.85, 1.1), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0, 0)
    me.materials.append(MAT_FUSELAGE)
    smooth_shade(me)
    return o

fuselage = make_fuselage("fuselage", apache)

# Tail boom (long cone tapered)
tail_boom = smooth_cone("tail_boom", r1=0.25, r2=0.15, depth=3.0, segs=20, loc=(-2.5, 0.10, 0), parent=apache, mat=MAT_FUSELAGE)
tail_boom.rotation_euler = (0, math.radians(-90), 0)

# Tail fin (vertical)
tail_fin = beveled_cube("tail_fin", (0.50, 0.85, 0.06), bevel_offset=0.05, bevel_segments=3, loc=(-3.85, 0.50, 0), parent=apache, mat=MAT_FUSELAGE)

# Horizontal stabilizers
for side, dz in [("L", 0.40), ("R", -0.40)]:
    stab = beveled_cube(f"hstab_{side}", (0.60, 0.06, 0.40), bevel_offset=0.04, bevel_segments=3, loc=(-3.50, 0.20, dz), parent=apache, mat=MAT_FUSELAGE)

# --- Tandem cockpit (2 sieges visibles à travers canopée) ---------
# front cockpit canopy
front_canopy = smooth_sphere("front_canopy", r=0.45, segs=24, rings=18, loc=(1.50, 0.40, 0), parent=apache, mat=MAT_CANOPY, scale=(1.2, 0.9, 1.0))
# back cockpit canopy
back_canopy = smooth_sphere("back_canopy", r=0.45, segs=24, rings=18, loc=(0.60, 0.45, 0), parent=apache, mat=MAT_CANOPY, scale=(1.2, 0.9, 1.0))
# cockpit frame between canopies
cockpit_frame = beveled_cube("cockpit_frame", (0.05, 0.40, 0.85), bevel_offset=0.02, bevel_segments=2, loc=(1.05, 0.40, 0), parent=apache, mat=MAT_FUSELAGE_DARK)

# 2 pilots inside
pilots = []
for i, (px, name) in enumerate([(1.50, "front_pilot"), (0.60, "back_pilot")]):
    p_p = empty(f"{name}_p", (px, 0.30, 0), parent=apache)
    # torso
    torso = beveled_cube(f"{name}_torso", (0.20, 0.30, 0.30), bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=p_p, mat=MAT_PILOT_SUIT)
    # helmet
    helmet = smooth_sphere(f"{name}_helmet", r=0.17, segs=20, rings=14, loc=(0, 0.30, 0), parent=p_p, mat=MAT_PILOT_HELMET)
    # visor (dark green tactical)
    visor = smooth_sphere(f"{name}_visor", r=0.15, segs=18, rings=12, loc=(0.04, 0.30, 0), parent=p_p, mat=MAT_PILOT_VISOR)
    visor.scale = (0.5, 0.6, 1.0)
    pilots.append(helmet)

# --- Main rotor system (4 blades, rotating ultra fast) ------------
rotor_mast = smooth_cone("rotor_mast", r1=0.10, r2=0.08, depth=0.6, segs=12, loc=(1.0, 0.80, 0), parent=apache, mat=MAT_ROTOR_HUB)
rotor_mast.rotation_euler = (math.radians(90), 0, 0)
rotor_hub = smooth_sphere("rotor_hub", r=0.20, segs=18, rings=14, loc=(1.0, 1.15, 0), parent=apache, mat=MAT_ROTOR_HUB)
main_rotor_p = empty("main_rotor_p", (1.0, 1.20, 0), parent=apache)
# 4 main blades
for k in range(4):
    ka = k * (math.pi / 2)
    blade = beveled_cube(f"main_blade_{k}", (3.5, 0.04, 0.20), bevel_offset=0.03, bevel_segments=3, loc=(0, 0, 0), parent=main_rotor_p, mat=MAT_ROTOR_BLADE)
    blade.rotation_euler = (0, ka, 0)

# --- Tail rotor (4 blades vertical) ---------------------------------
tail_rotor_p = empty("tail_rotor_p", (-4.10, 0.40, 0.20), parent=apache)
tail_rotor_hub = smooth_sphere("tail_rotor_hub", r=0.06, segs=14, rings=10, loc=(0, 0, 0), parent=tail_rotor_p, mat=MAT_ROTOR_HUB)
for k in range(4):
    ka = k * (math.pi / 2)
    blade = beveled_cube(f"tail_blade_{k}", (0.04, 0.04, 0.55), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0), parent=tail_rotor_p, mat=MAT_ROTOR_BLADE)
    blade.rotation_euler = (0, 0, ka)

# --- 2 stub wings (lateral) with hardpoints -----------------------
for side, dz in [("L", 0.70), ("R", -0.70)]:
    wing = beveled_cube(f"wing_{side}", (0.60, 0.06, 0.80), bevel_offset=0.05, bevel_segments=3, loc=(0.10, -0.10, dz), parent=apache, mat=MAT_FUSELAGE)
    # 4 hardpoints (small pylons under wing)
    for k in range(4):
        kz_off = -0.30 + k * 0.20
        pylon = beveled_cube(f"pylon_{side}_{k}", (0.08, 0.10, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(0.10, -0.18, dz + kz_off), parent=apache, mat=MAT_FUSELAGE_DARK)

# --- 6 Hellfire missiles (3 par côté, inner hardpoints) ---------
for side, dz in [("L", 0.70), ("R", -0.70)]:
    for k in range(3):
        kz_off = -0.25 + k * 0.15
        m_p = empty(f"missile_{side}_{k}_p", (0.10, -0.30, dz + kz_off), parent=apache)
        # body
        body = smooth_cone(f"missile_{side}_{k}", r1=0.05, r2=0.05, depth=0.65, segs=14, loc=(0, 0, 0), parent=m_p, mat=MAT_MISSILE)
        body.rotation_euler = (0, math.radians(90), 0)
        # nose
        nose = smooth_cone(f"missile_{side}_{k}_nose", r1=0.05, r2=0.0, depth=0.15, segs=10, loc=(0.40, 0, 0), parent=m_p, mat=MAT_MISSILE_TIP)
        nose.rotation_euler = (0, math.radians(90), 0)
        # 4 fins
        for fk in range(4):
            fa = fk * (math.pi / 2)
            fin = beveled_cube(f"missile_{side}_{k}_fin_{fk}", (0.08, 0.025, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(-0.25, math.sin(fa) * 0.07, math.cos(fa) * 0.07), parent=m_p, mat=MAT_MISSILE)
            fin.rotation_euler = (fa, 0, 0)

# --- 2 rocket pods (outer hardpoints, 19 tubes each) ------------
rocket_pods = []
for side, dz in [("L", 0.80), ("R", -0.80)]:
    pod_p = empty(f"rocket_pod_{side}", (0.10, -0.45, dz), parent=apache)
    # main pod body (cylinder)
    pod = smooth_cone(f"rocket_pod_{side}_body", r1=0.18, r2=0.18, depth=0.70, segs=24, loc=(0, 0, 0), parent=pod_p, mat=MAT_ROCKET_POD)
    pod.rotation_euler = (0, math.radians(90), 0)
    # 19 tubes (visible at end)
    # arrange in hexagonal pattern : 1 center + 6 inner + 12 outer
    tube_positions = [(0, 0)]
    for k in range(6):
        ka = k * (math.pi / 3)
        tube_positions.append((math.cos(ka) * 0.07, math.sin(ka) * 0.07))
    for k in range(12):
        ka = k * (math.pi / 6)
        tube_positions.append((math.cos(ka) * 0.13, math.sin(ka) * 0.13))
    for k, (tx, tz) in enumerate(tube_positions[:19]):
        tube = smooth_cone(f"rocket_tube_{side}_{k}", r1=0.025, r2=0.025, depth=0.08, segs=10, loc=(0.32, tx, tz), parent=pod_p, mat=MAT_ROCKET_TUBE)
        tube.rotation_euler = (0, math.radians(90), 0)
    rocket_pods.append(pod_p)

# --- Chain gun M230 sous nez (rotatif) -------------------------
chain_gun_p = empty("chain_gun_p", (2.00, -0.10, 0), parent=apache)
# mount
mount = smooth_sphere("chain_gun_mount", r=0.15, segs=18, rings=14, loc=(0, 0, 0), parent=chain_gun_p, mat=MAT_CHAIN_GUN)
# barrel
chain_barrel = smooth_cone("chain_barrel", r1=0.05, r2=0.05, depth=1.2, segs=14, loc=(0.60, -0.10, 0), parent=chain_gun_p, mat=MAT_CHAIN_GUN)
chain_barrel.rotation_euler = (0, 0, math.radians(90))

# --- 2 sensors FLIR sur nez ----------------------------------------
sensors = []
for i, (sx, sy, sz, mat_lens) in enumerate([
    (2.20, 0.05, 0, MAT_FLIR_LENS),
    (2.10, 0.25, 0, MAT_FLIR_LENS),
]):
    s_p = empty(f"sensor_{i}", (sx, sy, sz), parent=apache)
    housing = smooth_sphere(f"sensor_{i}_h", r=0.12, segs=16, rings=12, loc=(0, 0, 0), parent=s_p, mat=MAT_SENSOR)
    lens = smooth_sphere(f"sensor_{i}_lens", r=0.10, segs=14, rings=10, loc=(0.05, 0, 0), parent=s_p, mat=mat_lens)
    sensors.append(s_p)

# --- 4 landing skids -----------------------------------------------
for side, dz in [("L", 0.45), ("R", -0.45)]:
    # main strut
    strut1 = smooth_cone(f"skid_strut_{side}_F", r1=0.04, r2=0.04, depth=0.5, segs=10, loc=(0.50, -0.45, dz), parent=apache, mat=MAT_SKID)
    strut2 = smooth_cone(f"skid_strut_{side}_B", r1=0.04, r2=0.04, depth=0.5, segs=10, loc=(-0.80, -0.45, dz), parent=apache, mat=MAT_SKID)
    # skid (long horizontal cone)
    skid = smooth_cone(f"skid_{side}", r1=0.05, r2=0.05, depth=2.5, segs=14, loc=(-0.15, -0.70, dz), parent=apache, mat=MAT_SKID)
    skid.rotation_euler = (0, math.radians(90), 0)
    # skid curl-up tips
    for x_tip in [-1.4, 1.1]:
        tip = smooth_cone(f"skid_tip_{side}_{x_tip}", r1=0.05, r2=0.03, depth=0.20, segs=10, loc=(x_tip, -0.62, dz), parent=apache, mat=MAT_SKID)
        tip.rotation_euler = (0, math.radians(60), 0)

# --- 2 turbojets émissifs --------------------------------------
for side, dz in [("L", 0.50), ("R", -0.50)]:
    # turbojet housing
    jet = smooth_cone(f"jet_{side}", r1=0.20, r2=0.18, depth=0.85, segs=18, loc=(-0.55, 0.55, dz), parent=apache, mat=MAT_TURBOJET)
    jet.rotation_euler = (0, math.radians(90), 0)
    # exhaust port
    exhaust = smooth_sphere(f"jet_{side}_exhaust", r=0.16, segs=18, rings=12, loc=(-1.05, 0.55, dz), parent=apache, mat=MAT_EXHAUST_HEAT, scale=(0.4, 1.0, 1.0))

# --- nav lights ---------------------------------------------------
# port (red), starboard (green), tail (white)
nav_port = smooth_sphere("nav_port", r=0.05, segs=12, rings=8, loc=(0.10, -0.15, 0.80), parent=apache, mat=MAT_NAV_RED)
nav_starboard = smooth_sphere("nav_starboard", r=0.05, segs=12, rings=8, loc=(0.10, -0.15, -0.80), parent=apache, mat=MAT_NAV_GREEN)
nav_tail = smooth_sphere("nav_tail", r=0.06, segs=12, rings=8, loc=(-4.05, 0.40, 0), parent=apache, mat=MAT_NAV_WHITE)

# --- US flag sur fuselage arrière -----------------------------
for k in range(5):
    ky = 0.20 + k * 0.05
    mat = MAT_FLAG_R if k % 2 == 0 else MAT_FLAG_W
    stripe = beveled_cube(f"flag_stripe_{k}", (0.08, 0.04, 0.25), bevel_offset=0.01, bevel_segments=2, loc=(-1.50, ky, 0.45), parent=apache, mat=mat)
canton = beveled_cube("flag_canton", (0.08, 0.08, 0.12), bevel_offset=0.01, bevel_segments=2, loc=(-1.50, 0.32, 0.34), parent=apache, mat=MAT_FLAG_B)

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

# Apache : circular flight + banking + altitude variation
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    angle = tt * math.pi * 2.0
    cx = math.cos(angle) * 5.0
    cz = math.sin(angle) * 3.5
    cy = 6.0 + math.sin(tt * math.pi * 4.0) * 0.4
    kf_loc(apache, f, (cx, cy, cz))
    heading = -angle + math.pi / 2
    bank = math.radians(18) * math.sin(angle)
    pitch = math.radians(6) * math.cos(tt * math.pi * 3.0)
    kf_rot(apache, f, (pitch, heading, bank))

# Main rotor : ULTRA FAST (30 turns/loop = 60π·t)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(main_rotor_p, f, (0, tt * math.pi * 60, 0))

# Tail rotor : also ultra fast
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(tail_rotor_p, f, (tt * math.pi * 80, 0, 0))

# Chain gun sweeps left/right ±30°
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = math.radians(30) * math.sin(tt * math.pi * 4.0)
    kf_rot(chain_gun_p, f, (0, angle, 0))

# 2 sensors pivot
for i, s_p in enumerate(sensors):
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(15) * math.sin(tt * math.pi * 3.0 + i * 0.5)
        kf_rot(s_p, f, (0, delta, 0))

# Pilots head bob
for helmet in pilots:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        bob = math.radians(3) * math.sin(tt * math.pi * 4.0)
        kf_rot(helmet, f, (bob, 0, 0))

# 2 turbojets exhaust pulse
for side, dz in [("L", 0.50), ("R", -0.50)]:
    exhaust = bpy.data.objects.get(f"jet_{side}_exhaust")
    if exhaust:
        for f in range(1, FRAMES + 1, 2):
            tt = (f - 1) / (FRAMES - 1)
            s = 1.0 + 0.25 * math.sin(tt * math.pi * 10.0)
            kf_scale(exhaust, f, (0.4 * s, 1.0 * s, 1.0 * s))

# Nav lights blink
for nav in [nav_port, nav_starboard, nav_tail]:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 12.0)
        kf_scale(nav, f, (s, s, s))

# Clouds drift slow
for i in range(4):
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
print(f"[proc_apache] wrote {OUT}")
