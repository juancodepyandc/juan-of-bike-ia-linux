"""
proc_dragon_skull_desert.py — 182e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie).

Squelette de dragon géant dans désert :
- crâne dragon géant articulé (mandibule open + 12 crocs + 2 orbites + 4 cornes + collerette épines)
- 6 vertèbres connectées (cou + dos + queue)
- 2 fémurs + tibias (jambes squelettiques)
- cage thoracique 8 côtes
- 2 omoplates + clavicules
- sable désert dunes + 6 cactus + 4 rochers
- 5 vautours volant
- 12 ossements éparpillés
- mirages volumiques alpha
- soleil intense + 3 halos
- ciel orange désert
- 4 lézards
- caravane (3 chameaux + 2 voyageurs)
- 30 grains sable drift

Animations multi-axes simultanées :
- crâne mandibule subtle open/close
- 5 vautours flap + orbit
- 4 lézards drift + tilt
- 30 grains sable drift
- chameaux walk slow
- soleil pulse + halos breathe
- mirages drift

Sortie : output/3d/pbr_skull_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_skull_proc.glb"))

random.seed(0x5C0177)


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
MAT_SKY = make_mat("sky_desert", (1.0, 0.65, 0.30), roughness=1.0, emi=(0.65, 0.40, 0.20), emi_strength=1.2)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.45), roughness=0.0, emi=(1.0, 0.85, 0.45), emi_strength=14.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.85, 0.45), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.45), emi_strength=3.5)
MAT_SAND = make_mat("sand", (0.85, 0.65, 0.30), roughness=0.85, emi=(0.40, 0.30, 0.12), emi_strength=0.4)
MAT_SAND_DARK = make_mat("sand_dark", (0.55, 0.40, 0.20), roughness=0.95)
MAT_BONE = make_mat("bone", (0.92, 0.88, 0.78), roughness=0.5, emi=(0.40, 0.38, 0.32), emi_strength=0.4)
MAT_BONE_DARK = make_mat("bone_dark", (0.70, 0.60, 0.50), roughness=0.65)
MAT_BONE_TEETH = make_mat("bone_teeth", (0.95, 0.92, 0.85), roughness=0.30, emi=(0.45, 0.42, 0.38), emi_strength=0.5)
MAT_EYE_SOCKET = make_mat("eye_socket", (0.10, 0.05, 0.05), roughness=0.85)
MAT_VULTURE = make_mat("vulture", (0.20, 0.15, 0.12), roughness=0.6)
MAT_VULTURE_HEAD = make_mat("vulture_head", (0.85, 0.50, 0.30), roughness=0.6, emi=(0.30, 0.18, 0.08), emi_strength=0.4)
MAT_CACTUS = make_mat("cactus", (0.25, 0.55, 0.20), roughness=0.7, emi=(0.10, 0.25, 0.08), emi_strength=0.4)
MAT_ROCK = make_mat("rock_desert", (0.45, 0.32, 0.20), roughness=0.95)
MAT_CAMEL = make_mat("camel", (0.85, 0.65, 0.40), roughness=0.65, emi=(0.30, 0.22, 0.12), emi_strength=0.4)
MAT_TRAVELER = make_mat("traveler", (0.55, 0.40, 0.30), roughness=0.6)
MAT_LIZARD = make_mat("lizard", (0.45, 0.35, 0.20), roughness=0.5, emi=(0.18, 0.12, 0.06), emi_strength=0.4)
MAT_MIRAGE = make_mat("mirage", (0.85, 0.75, 0.50), roughness=0.7, alpha=0.40, emi=(0.55, 0.45, 0.25), emi_strength=1.5)


# --- backdrop : desert sky -----------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)
# sun + halos
sun_p = empty("sun_p", (8, 13, 8))
sun = smooth_sphere("sun", r=1.6, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.5, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=3.5, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# desert ground sand
ground = beveled_cube("sand_floor", (40, 0.3, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.15, 0), mat=MAT_SAND)

# 6 sand dunes (rolling hills)
for dk in range(6):
    a = dk * (math.pi * 2 / 6) + random.uniform(-0.2, 0.2)
    r = random.uniform(8, 15)
    dx = math.cos(a) * r
    dz = math.sin(a) * r * 0.7
    dh = random.uniform(0.8, 1.6)
    smooth_sphere(f"dune_{dk}", r=random.uniform(3, 5), segs=16, rings=12, loc=(dx, dh / 2, dz), mat=MAT_SAND, scale=(1.0, dh / 3, 1.0))


# --- CRÂNE DRAGON GÉANT articulé ---------------------------------------
skull_p = empty("skull", (0, 0.5, 0))

# CRANIUM (main skull dome, elongated dragon)
cranium = smooth_sphere("cranium", r=1.2, segs=26, rings=20, loc=(0, 1.2, 0), parent=skull_p, mat=MAT_BONE, scale=(2.0, 1.0, 1.2))
# snout extension
snout = smooth_cone("snout", r1=0.9, r2=0.40, depth=2.0, segs=14, loc=(2.0, 1.1, 0), parent=skull_p, mat=MAT_BONE)
bp = bpy.data.objects.get("snout")
if bp:
    bp.rotation_euler = (0, 0, math.radians(-90))
# nasal cavity (dark)
smooth_sphere("nasal_cavity", r=0.20, segs=14, rings=10, loc=(2.5, 1.1, 0), parent=skull_p, mat=MAT_EYE_SOCKET)

# 2 ORBITES (eye sockets, dark) anatomical
for ek, ez in [("L", 0.55), ("R", -0.55)]:
    smooth_sphere(f"orbit_{ek}", r=0.30, segs=18, rings=14, loc=(1.0, 1.5, ez), parent=skull_p, mat=MAT_EYE_SOCKET)
    # bone ring around socket
    smooth_cone(f"orbit_ring_{ek}", r1=0.35, r2=0.30, depth=0.06, segs=18, loc=(1.0, 1.5, ez * 0.95), parent=skull_p, mat=MAT_BONE)

# 4 GRANDES CORNES (signature dragon)
horn_configs = [
    (-0.50, 2.20, 0.70),  # back-L
    (-0.50, 2.20, -0.70),  # back-R
    (0.30, 2.10, 0.50),  # mid-L
    (0.30, 2.10, -0.50),  # mid-R
]
for hk, (hx, hy, hz) in enumerate(horn_configs):
    horn = smooth_cone(f"horn_{hk}", r1=0.15, r2=0.0, depth=1.2, segs=10, loc=(hx, hy, hz), parent=skull_p, mat=MAT_BONE_DARK)
    horn.rotation_euler = (math.radians(-20 * (1 if hz > 0 else -1)), math.radians(20 - hk * 5), math.radians(-30 if hz > 0 else 30))

# 12 PETITES ÉPINES collerette
for sk in range(12):
    sa = sk * (math.pi * 2 / 12)
    sr = 0.85
    sx = math.cos(sa) * sr
    sy = 1.50
    sz = math.sin(sa) * sr
    spike = smooth_cone(f"frill_spike_{sk}", r1=0.06, r2=0.0, depth=0.25, segs=6, loc=(sx + 0.5, sy, sz), parent=skull_p, mat=MAT_BONE)
    spike.rotation_euler = (math.radians(20 * math.cos(sa)), 0, math.radians(20 * math.sin(sa)))

# MANDIBULE inférieure (articulée, slightly open)
jaw_p = empty("jaw_p", (1.0, 0.55, 0), parent=skull_p)
jaw_p.rotation_euler = (0, 0, math.radians(-15))  # mandible open
# jaw bone (V shape)
smooth_cone("jaw_main", r1=0.40, r2=0.25, depth=1.8, segs=14, loc=(0.40, -0.10, 0), parent=jaw_p, mat=MAT_BONE)
jb = bpy.data.objects.get("jaw_main")
if jb:
    jb.rotation_euler = (0, 0, math.radians(-90))
# jaw curve (rear thicker)
smooth_sphere("jaw_back", r=0.40, segs=18, rings=12, loc=(-0.10, 0, 0), parent=jaw_p, mat=MAT_BONE, scale=(1.0, 0.7, 1.2))

# 12 CROCS / DENTS dans bouche (6 supérieurs + 6 inférieurs)
# upper teeth (attached to snout)
for tk in range(6):
    tx = 0.50 + tk * 0.40
    smooth_cone(f"tooth_upper_{tk}", r1=0.08, r2=0.0, depth=0.30, segs=6, loc=(tx, 0.65, 0.30 if tk % 2 == 0 else -0.30), parent=skull_p, mat=MAT_BONE_TEETH)
    bp = bpy.data.objects.get(f"tooth_upper_{tk}")
    if bp:
        bp.rotation_euler = (math.radians(180), 0, 0)
# lower teeth (attached to jaw)
for tk in range(6):
    tx = 0.40 + tk * 0.30
    smooth_cone(f"tooth_lower_{tk}", r1=0.08, r2=0.0, depth=0.25, segs=6, loc=(tx, 0.10, 0.20 if tk % 2 == 0 else -0.20), parent=jaw_p, mat=MAT_BONE_TEETH)

# 2 fangs huge (canines)
for fk, fz in [("L", 0.30), ("R", -0.30)]:
    fang = smooth_cone(f"fang_{fk}", r1=0.12, r2=0.0, depth=0.50, segs=8, loc=(0.95, 0.55, fz), parent=skull_p, mat=MAT_BONE_TEETH)
    fang.rotation_euler = (math.radians(180), 0, 0)


# --- 6 VERTÈBRES (cou descendant vers dos) -----------------------------
spine_segs = []
for sk in range(6):
    vp = empty(f"vertebra_p_{sk}", (-1.5 - sk * 0.6, 0.6 - sk * 0.05, 0), parent=skull_p)
    spine_segs.append(vp)
    # main vertebra body
    smooth_sphere(f"vertebra_{sk}_b", r=0.30 - sk * 0.02, segs=14, rings=10, loc=(0, 0, 0), parent=vp, mat=MAT_BONE, scale=(1.0, 1.0, 1.2))
    # 4 spines top
    for spi in range(4):
        sa = spi * (math.pi * 2 / 4) + math.pi / 4
        sp_x = math.cos(sa) * 0.20
        sp_z = math.sin(sa) * 0.20
        sp_top = smooth_cone(f"vert_{sk}_sp_{spi}", r1=0.05, r2=0.0, depth=0.15, segs=4, loc=(sp_x, 0.20, sp_z), parent=vp, mat=MAT_BONE_DARK)
    # transverse process (ribs attach point)
    if sk < 4:
        smooth_cone(f"vert_{sk}_tp", r1=0.04, r2=0.0, depth=0.30, segs=4, loc=(0, 0, 0.30 if sk % 2 == 0 else -0.30), parent=vp, mat=MAT_BONE_DARK)


# --- 8 CÔTES (cage thoracique) -----------------------------------------
ribs_p = empty("ribs_p", (-3, 0.5, 0), parent=skull_p)
for rk in range(4):
    rx = -rk * 0.6
    # 2 ribs per pair (L + R)
    for side_k, sign in [(0, 1), (1, -1)]:
        rib_p = empty(f"rib_p_{rk}_{side_k}", (rx, 0, sign * 0.25), parent=ribs_p)
        # 3 segments forming curved rib
        cur = rib_p
        for sg in range(3):
            seg = empty(f"rib_seg_p_{rk}_{side_k}_{sg}", (0, -0.30, sign * 0.20), parent=cur)
            seg.rotation_euler = (0, 0, math.radians(20 * sign))
            smooth_cone(f"rib_{rk}_{side_k}_{sg}", r1=0.05 - sg * 0.005, r2=0.05 - sg * 0.005, depth=0.40, segs=6, loc=(0, -0.20, 0), parent=seg, mat=MAT_BONE)
            cur = seg


# --- 2 OMOPLATES + clavicules -----------------------------------------
for sk, sz in [(0, 0.7), (1, -0.7)]:
    shoulder_p = empty(f"shoulder_p_{sk}", (-2, 0.3, sz), parent=skull_p)
    # omoplate (flat sphere)
    smooth_sphere(f"omoplate_{sk}", r=0.30, segs=14, rings=10, loc=(0, 0, 0), parent=shoulder_p, mat=MAT_BONE, scale=(1.4, 1.0, 0.30))


# --- 2 FÉMURS + tibias (jambes squelettiques) ------------------------
for lk, lz in [(0, 0.65), (1, -0.65)]:
    leg_p = empty(f"leg_p_{lk}", (-3.5, 0.20, lz), parent=skull_p)
    # femur
    smooth_cone(f"femur_{lk}", r1=0.15, r2=0.10, depth=1.2, segs=10, loc=(0, -0.6, 0), parent=leg_p, mat=MAT_BONE)
    # knee joint
    knee_p = empty(f"knee_p_{lk}", (0, -1.2, 0), parent=leg_p)
    knee_p.rotation_euler = (0, 0, math.radians(15))
    # tibia
    smooth_cone(f"tibia_{lk}", r1=0.10, r2=0.06, depth=1.0, segs=10, loc=(0, -0.50, 0), parent=knee_p, mat=MAT_BONE)
    # foot bone (claws indication)
    for ck in range(3):
        ca = ck * (math.pi * 2 / 3)
        smooth_cone(f"claw_{lk}_{ck}", r1=0.04, r2=0.0, depth=0.20, segs=4, loc=(math.cos(ca) * 0.10, -1.00, math.sin(ca) * 0.10), parent=knee_p, mat=MAT_BONE_DARK)


# --- 6 CACTUS -----------------------------------------------------------
cactus_list = []
for ck in range(6):
    a = ck * (math.pi * 2 / 6) + 0.5
    r = random.uniform(6, 11)
    cx = math.cos(a) * r
    cz = math.sin(a) * r * 0.7
    cp = empty(f"cactus_{ck}_p", (cx, 0, cz))
    cactus_list.append(cp)
    # main trunk
    smooth_cone(f"cactus_{ck}_main", r1=0.25, r2=0.22, depth=2.0, segs=10, loc=(0, 1.0, 0), parent=cp, mat=MAT_CACTUS)
    # 2 arms branches
    for bk, ba in [(0, 0.5), (1, -0.5)]:
        # arm horizontal then up
        arm_p = empty(f"cactus_{ck}_arm_p_{bk}", (math.cos(ba) * 0.4, 1.2, math.sin(ba) * 0.4), parent=cp)
        smooth_cone(f"cactus_{ck}_arm_h_{bk}", r1=0.15, r2=0.12, depth=0.40, segs=8, loc=(math.cos(ba) * 0.20, 0, math.sin(ba) * 0.20), parent=arm_p, mat=MAT_CACTUS)
        # vertical part going up
        smooth_cone(f"cactus_{ck}_arm_v_{bk}", r1=0.12, r2=0.10, depth=0.80, segs=8, loc=(math.cos(ba) * 0.40, 0.40, math.sin(ba) * 0.40), parent=arm_p, mat=MAT_CACTUS)
    # spines (small cones)
    for sk in range(8):
        sa = sk * (math.pi * 2 / 8)
        sy_off = 0.5 + (sk % 4) * 0.3
        smooth_cone(f"cactus_{ck}_sp_{sk}", r1=0.012, r2=0.0, depth=0.06, segs=4, loc=(math.cos(sa) * 0.25, sy_off, math.sin(sa) * 0.25), parent=cp, mat=MAT_BONE)


# --- 4 ROCHERS désertiques ---------------------------------------------
for rk in range(4):
    rx = random.uniform(-12, 12)
    rz = random.uniform(-5, 8)
    rh = random.uniform(0.5, 1.0)
    smooth_sphere(f"rock_{rk}", r=random.uniform(0.6, 1.0), segs=14, rings=10, loc=(rx, rh, rz), mat=MAT_ROCK, scale=(1.2, rh, 1.1))


# --- 5 VAUTOURS volant -------------------------------------------------
vultures = []
for vi in range(5):
    a = vi * (math.pi * 2 / 5) + random.uniform(-0.2, 0.2)
    r = random.uniform(4, 9)
    vy = random.uniform(5, 9)
    vp = empty(f"vulture_{vi}_p", (math.cos(a) * r, vy, math.sin(a) * r * 0.7))
    vultures.append({"p": vp, "a": a, "r": r, "vy": vy, "phase": vi * 0.40})
    # body
    smooth_sphere(f"vulture_{vi}_body", r=0.20, segs=14, rings=10, loc=(0, 0, 0), parent=vp, mat=MAT_VULTURE, scale=(1.5, 0.85, 0.85))
    # head red bald
    smooth_sphere(f"vulture_{vi}_head", r=0.12, segs=12, rings=8, loc=(0.20, 0.05, 0), parent=vp, mat=MAT_VULTURE_HEAD)
    # beak
    smooth_cone(f"vulture_{vi}_beak", r1=0.04, r2=0.0, depth=0.10, segs=6, loc=(0.32, 0.02, 0), parent=vp, mat=MAT_BONE_DARK)
    # 2 wings
    wL = empty(f"vulture_{vi}_wL", (0, 0.04, 0.10), parent=vp)
    wR = empty(f"vulture_{vi}_wR", (0, 0.04, -0.10), parent=vp)
    smooth_sphere(f"vulture_{vi}_wL_b", r=0.20, segs=14, rings=8, loc=(0, 0, 0.30), parent=wL, mat=MAT_VULTURE, scale=(0.5, 0.05, 2.0))
    smooth_sphere(f"vulture_{vi}_wR_b", r=0.20, segs=14, rings=8, loc=(0, 0, -0.30), parent=wR, mat=MAT_VULTURE, scale=(0.5, 0.05, 2.0))
    vultures[vi]["wL"] = wL
    vultures[vi]["wR"] = wR


# --- CARAVANE (3 CHAMEAUX + 2 VOYAGEURS) -------------------------------
caravan_p = empty("caravan_p", (10, 0, 6))
camels = []
for ck in range(3):
    cx = ck * 1.5
    cp = empty(f"camel_{ck}_p", (cx, 0, 0), parent=caravan_p)
    camels.append({"p": cp, "phase": ck * 0.40})
    # body
    smooth_sphere(f"camel_{ck}_body", r=0.55, segs=18, rings=14, loc=(0, 1.0, 0), parent=cp, mat=MAT_CAMEL, scale=(1.6, 0.85, 1.0))
    # 2 hump (signature)
    smooth_sphere(f"camel_{ck}_hump1", r=0.30, segs=14, rings=10, loc=(-0.20, 1.50, 0), parent=cp, mat=MAT_CAMEL, scale=(1.0, 1.0, 1.0))
    smooth_sphere(f"camel_{ck}_hump2", r=0.30, segs=14, rings=10, loc=(0.20, 1.45, 0), parent=cp, mat=MAT_CAMEL, scale=(1.0, 1.0, 1.0))
    # head + neck (curved up)
    neck = smooth_cone(f"camel_{ck}_neck", r1=0.18, r2=0.15, depth=0.85, segs=10, loc=(0.80, 1.45, 0), parent=cp, mat=MAT_CAMEL)
    neck.rotation_euler = (0, 0, math.radians(-55))
    smooth_sphere(f"camel_{ck}_head", r=0.18, segs=14, rings=10, loc=(1.20, 1.85, 0), parent=cp, mat=MAT_CAMEL)
    # 4 legs
    for lk, (lx, lz) in enumerate([(-0.30, -0.30), (0.30, -0.30), (-0.30, 0.30), (0.30, 0.30)]):
        smooth_cone(f"camel_{ck}_leg_{lk}", r1=0.08, r2=0.07, depth=1.0, segs=8, loc=(lx, 0.50, lz), parent=cp, mat=MAT_CAMEL)
    # tail
    smooth_cone(f"camel_{ck}_tail", r1=0.04, r2=0.0, depth=0.40, segs=6, loc=(-0.55, 1.05, 0), parent=cp, mat=MAT_CAMEL)
# 2 voyageurs (silhouettes simples on first/last camel)
for ti, (tx, ty, tz) in [(0, (0, 1.85, 0)), (1, (3, 1.85, 0))]:
    tp = empty(f"traveler_{ti}_p", (tx, ty, tz), parent=caravan_p)
    smooth_cone(f"traveler_{ti}_body", r1=0.12, r2=0.18, depth=0.50, segs=8, loc=(0, 0.25, 0), parent=tp, mat=MAT_TRAVELER)
    smooth_sphere(f"traveler_{ti}_head", r=0.10, segs=12, rings=8, loc=(0, 0.60, 0), parent=tp, mat=MAT_TRAVELER)


# --- 4 LÉZARDS au sol --------------------------------------------------
lizards = []
for lk in range(4):
    a = lk * (math.pi * 2 / 4) + 0.3
    r = random.uniform(4, 8)
    lx = math.cos(a) * r
    lz = math.sin(a) * r * 0.6
    lp = empty(f"lizard_{lk}_p", (lx, 0.05, lz))
    lizards.append({"p": lp, "phase": lk * 0.30, "base": (lx, 0.05, lz)})
    # body elongated
    smooth_sphere(f"lizard_{lk}_body", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_LIZARD, scale=(2.5, 0.50, 0.85))
    # head
    smooth_sphere(f"lizard_{lk}_head", r=0.08, segs=10, rings=6, loc=(0.20, 0, 0), parent=lp, mat=MAT_LIZARD)
    # tail
    smooth_cone(f"lizard_{lk}_tail", r1=0.05, r2=0.0, depth=0.30, segs=6, loc=(-0.20, 0, 0), parent=lp, mat=MAT_LIZARD)
    # 4 legs
    for lgk, (lx_off, lz_off) in enumerate([(0.10, 0.10), (-0.10, 0.10), (0.10, -0.10), (-0.10, -0.10)]):
        smooth_cone(f"lizard_{lk}_leg_{lgk}", r1=0.03, r2=0.0, depth=0.10, segs=4, loc=(lx_off, -0.05, lz_off), parent=lp, mat=MAT_LIZARD)


# --- 12 OSSEMENTS éparpillés ----------------------------------------
for bk in range(12):
    bx = random.uniform(-10, 10)
    bz = random.uniform(-6, 8)
    if abs(bx) < 4 and abs(bz) < 4:
        continue  # skip near skull
    # random bone shape (sphere or cylinder)
    if bk % 2 == 0:
        smooth_sphere(f"bone_frag_{bk}", r=random.uniform(0.15, 0.25), segs=10, rings=6, loc=(bx, 0.10, bz), mat=MAT_BONE, scale=(1.4, 0.4, 0.6))
    else:
        bone = smooth_cone(f"bone_frag_{bk}", r1=0.08, r2=0.06, depth=random.uniform(0.4, 0.7), segs=6, loc=(bx, 0.10, bz), mat=MAT_BONE)
        bone.rotation_euler = (0, 0, math.radians(random.uniform(60, 90)))


# --- 3 MIRAGES volumiques --------------------------------------------
for mi in range(3):
    a = mi * (math.pi * 2 / 3) + 0.5
    r = random.uniform(8, 12)
    mx = math.cos(a) * r
    mz = math.sin(a) * r * 0.7
    smooth_sphere(f"mirage_{mi}", r=random.uniform(1.0, 2.0), segs=14, rings=8, loc=(mx, 0.5, mz), mat=MAT_MIRAGE, scale=(2.5, 0.15, 1.5))


# --- 30 GRAINS sable drift ------------------------------------------
sand_grains = []
for gk in range(30):
    gx = random.uniform(-12, 12)
    gy = random.uniform(0.3, 3)
    gz = random.uniform(-5, 7)
    grain = smooth_sphere(f"grain_{gk}", r=random.uniform(0.04, 0.08), segs=8, rings=6, loc=(gx, gy, gz), mat=MAT_SAND)
    grain["_base"] = (gx, gy, gz)
    grain["_phase"] = gk * 0.15
    sand_grains.append(grain)


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

    # mandible subtle open/close (slight wind effect)
    jaw_open = math.radians(-15 + 5 * math.sin(2 * math.pi * tt * 0.4))
    kf(jaw_p, f, "rotation_euler", (0, 0, jaw_open))

    # 5 vultures flap + orbit
    for vd in vultures:
        ang = vd["a"] + tt * 2 * math.pi * 0.3
        bx_ = math.cos(ang) * vd["r"]
        bz_ = math.sin(ang) * vd["r"] * 0.7
        by_ = vd["vy"] + 0.30 * math.sin(2 * math.pi * tt * 1.0 + vd["phase"])
        kf(vd["p"], f, "location", (bx_, by_, bz_))
        kf(vd["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(45) * math.sin(2 * math.pi * tt * 6 + vd["phase"])
        kf(vd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(vd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 4 lizards drift + tilt
    for lz in lizards:
        bx_, by_, bz_ = lz["base"]
        ph = lz["phase"]
        nx = bx_ + 0.30 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi)
        nz = bz_ + 0.20 * math.cos(2 * math.pi * tt * 0.8 + ph * math.pi)
        kf(lz["p"], f, "location", (nx, by_, nz))
        kf(lz["p"], f, "rotation_euler", (0, math.radians(180 * tt + ph * 60), 0))

    # caravane : walk slow (drift X)
    cw_x = 10 + 3 * math.sin(2 * math.pi * tt * 0.2)
    kf(caravan_p, f, "location", (cw_x, 0, 6))

    # 3 camels subtle bob
    for ci, camel in enumerate(camels):
        ph = camel["phase"]
        ny = 0 + 0.06 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        cx = ci * 1.5
        kf(camel["p"], f, "location", (cx, ny, 0))

    # 30 sand grains drift
    for gr in sand_grains:
        bx_, by_, bz_ = gr["_base"]
        ph = gr["_phase"]
        nx = bx_ + 0.40 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        ny = by_ + 0.25 * math.cos(2 * math.pi * tt * 0.8 + ph * math.pi)
        nz = bz_ + 0.30 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(gr, f, "location", (nx, ny, nz))

    # sun pulse + halos breathe
    sp = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 1.5)
    kf(sun, f, "scale", (sp, sp, sp))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_dragon_skull_desert] wrote {OUT}")
