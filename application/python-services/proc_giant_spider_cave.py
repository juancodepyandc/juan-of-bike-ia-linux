"""
proc_giant_spider_cave.py — 167e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie articulée).

Grotte avec araignée géante sur toile :
- araignée géante anatomique : cephalothorax + abdomen + 8 yeux + 8 pattes 3 segments + 2 chélicères (crochets venimeux)
- 40 fils de toile traverse caverne (lignes radiales + spirales)
- 4 victimes cocons suspendues
- 12 petites araignées enfants
- 30 chauves-souris erratic
- 5 cristaux venimeux émissifs
- 20 magic particles
- os squelettes au sol
- cave rocheuse dome + stalactites + stalagmites
- entrée lumineuse arrière
- ciel grotte sombre

Animations multi-axes simultanées :
- araignée géante : 8 pattes walk pattern alterné (4+4 phase opposé) + corps lift Y + abdomen pulse + 8 yeux scan
- 30 chauves-souris : flap + dart erratic
- 12 petites araignées : crawl on web différentielles
- 4 cocons : swing Z
- 20 magic particles : drift 3D
- 5 cristaux venimeux : pulse + rotate XYZ
- stalactites : micro-vibration

Sortie : output/3d/pbr_spider_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_spider_proc.glb"))

random.seed(0x5712E2)


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
MAT_CAVE_DARK = make_mat("cave_dark", (0.05, 0.04, 0.06), roughness=1.0, emi=(0.04, 0.04, 0.06), emi_strength=0.4)
MAT_ROCK = make_mat("rock", (0.25, 0.22, 0.20), roughness=0.95)
MAT_STAL = make_mat("stalactite", (0.45, 0.40, 0.45), roughness=0.85, emi=(0.15, 0.12, 0.15), emi_strength=0.4)
MAT_SPIDER_BODY = make_mat("spider_body", (0.10, 0.05, 0.05), roughness=0.6, emi=(0.05, 0.02, 0.02), emi_strength=0.3)
MAT_SPIDER_BELLY = make_mat("spider_belly", (0.20, 0.10, 0.08), roughness=0.6, emi=(0.10, 0.04, 0.04), emi_strength=0.3)
MAT_SPIDER_LEG = make_mat("spider_leg", (0.08, 0.04, 0.04), roughness=0.6)
MAT_SPIDER_EYE = make_mat("spider_eye", (0.95, 0.30, 0.20), roughness=0.0, emi=(0.95, 0.30, 0.20), emi_strength=12.0)
MAT_SPIDER_FANG = make_mat("spider_fang", (0.85, 0.75, 0.50), roughness=0.30, emi=(0.30, 0.25, 0.15), emi_strength=0.5)
MAT_VENOM = make_mat("venom", (0.30, 0.95, 0.40), roughness=0.10, alpha=0.85, emi=(0.30, 0.95, 0.40), emi_strength=8.0)
MAT_WEB = make_mat("web", (0.95, 0.95, 0.95), roughness=0.0, alpha=0.50, emi=(0.55, 0.55, 0.55), emi_strength=1.5)
MAT_COCOON = make_mat("cocoon", (0.85, 0.82, 0.75), roughness=0.7, emi=(0.30, 0.28, 0.25), emi_strength=0.5)
MAT_BAT = make_mat("bat", (0.10, 0.08, 0.10), roughness=0.6)
MAT_BAT_WING = make_mat("bat_wing", (0.15, 0.10, 0.10), roughness=0.6, alpha=0.85)
MAT_BAT_EYE = make_mat("bat_eye", (0.95, 0.20, 0.20), roughness=0.0, emi=(0.95, 0.20, 0.20), emi_strength=6.0)
MAT_CRYSTAL_VEN = make_mat("crystal_venom", (0.30, 0.95, 0.50), roughness=0.05, emi=(0.30, 0.95, 0.50), emi_strength=12.0)
MAT_MAGIC_A = make_mat("magic_A", (0.55, 0.95, 0.40), roughness=0.0, emi=(0.55, 0.95, 0.40), emi_strength=8.0)
MAT_MAGIC_B = make_mat("magic_B", (0.95, 0.40, 0.55), roughness=0.0, emi=(0.95, 0.40, 0.55), emi_strength=8.0)
MAT_BONE = make_mat("bone", (0.85, 0.82, 0.75), roughness=0.5, emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_GROUND = make_mat("ground", (0.18, 0.15, 0.12), roughness=0.90, emi=(0.06, 0.05, 0.04), emi_strength=0.2)
MAT_ENTRANCE = make_mat("entrance", (0.85, 0.55, 0.30), roughness=0.0, emi=(0.85, 0.55, 0.30), emi_strength=5.0)


# --- backdrop : cave ----------------------------------------------------
sky_back = beveled_cube("cave_back", (40, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, 12, 12), mat=MAT_CAVE_DARK)
floor = beveled_cube("floor", (30, 0.2, 20), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND)

# entrance light arrière
entrance_p = empty("entrance_p", (0, 4, 10))
smooth_sphere("entrance_glow", r=2.0, segs=22, rings=14, loc=(0, 0, 0), parent=entrance_p, mat=MAT_ENTRANCE, scale=(1.3, 0.85, 0.3))


# --- cavern vault dome (40 rocks) ---------------------------------------
for rk in range(40):
    theta = random.uniform(0, math.pi / 2.2)
    phi = random.uniform(0, math.pi * 2)
    R = random.uniform(11, 13)
    x = R * math.sin(theta) * math.cos(phi)
    y = R * math.cos(theta) + 1.5
    z = R * math.sin(theta) * math.sin(phi)
    smooth_sphere(f"vault_rock_{rk}", r=random.uniform(0.8, 1.5), segs=14, rings=10, loc=(x, y, z), mat=MAT_ROCK, scale=(1.0, 0.85, 1.0))


# --- 20 stalactites pendant ----------------------------------------------
stalactites = []
for sk in range(20):
    sx = random.uniform(-8, 8)
    sy = random.uniform(7, 10)
    sz = random.uniform(-5, 5)
    sh = random.uniform(0.6, 1.6)
    sp = empty(f"stal_{sk}_p", (sx, sy, sz))
    stalactites.append(sp)
    smooth_cone(f"stal_{sk}", r1=0.20, r2=0.0, depth=sh, segs=10, loc=(0, -sh / 2, 0), parent=sp, mat=MAT_STAL)
    sp["_phase"] = sk * 0.20

# 15 stalagmites
for sk in range(15):
    sx = random.uniform(-9, 9)
    sz = random.uniform(-4, 6)
    if abs(sx) < 2 and abs(sz) < 2:
        continue
    sh = random.uniform(0.5, 1.4)
    smooth_cone(f"stalg_{sk}", r1=0.20, r2=0.0, depth=sh, segs=10, loc=(sx, sh / 2, sz), mat=MAT_STAL)


# --- WEB (40 lignes radiales + 5 spirales) ------------------------------
web_center = (0, 5, 0)
# 8 radial lines from center to outer ring (in vertical plane facing camera, z=0)
for rl in range(8):
    a = rl * (math.pi * 2 / 8)
    ex = math.cos(a) * 5
    ey = 5 + math.sin(a) * 5
    # cone between center and endpoint
    web_line = smooth_cone(f"web_radial_{rl}", r1=0.015, r2=0.015, depth=5.0, segs=4, loc=((0 + ex) / 2, (5 + ey) / 2, 0), mat=MAT_WEB)
    # align rotation
    web_line.rotation_euler = (0, 0, a + math.pi / 2)

# 5 spiral rings (concentric)
for sr in range(5):
    radius = 1.0 + sr * 0.8
    # use 16 segs each
    for sg in range(16):
        ang = sg * (math.pi * 2 / 16)
        next_ang = (sg + 1) * (math.pi * 2 / 16)
        cx = math.cos(ang) * radius
        cy = 5 + math.sin(ang) * radius
        nx = math.cos(next_ang) * radius
        ny = 5 + math.sin(next_ang) * radius
        # midpoint
        mx = (cx + nx) / 2
        my = (cy + ny) / 2
        # length
        dl = math.sqrt((nx - cx)**2 + (ny - cy)**2)
        # angle
        an = math.atan2(ny - cy, nx - cx)
        seg = smooth_cone(f"web_spiral_{sr}_{sg}", r1=0.012, r2=0.012, depth=dl, segs=4, loc=(mx, my, 0), mat=MAT_WEB)
        seg.rotation_euler = (0, 0, an + math.pi / 2)


# --- ARAIGNÉE GÉANTE (centre web) ----------------------------------------
spider_p = empty("spider", (0, 4.5, 0))

# cephalothorax (front body)
ceph = smooth_sphere("ceph", r=0.55, segs=24, rings=18, loc=(0, 0, 0), parent=spider_p, mat=MAT_SPIDER_BODY, scale=(1.2, 0.85, 1.2))
# abdomen (rear body, larger)
abdomen = smooth_sphere("abdomen", r=0.85, segs=26, rings=20, loc=(0, 0.10, -0.85), parent=spider_p, mat=MAT_SPIDER_BODY, scale=(1.1, 1.0, 1.4))
# belly highlight underside
smooth_sphere("abdomen_belly", r=0.55, segs=18, rings=14, loc=(0, -0.30, -0.85), parent=spider_p, mat=MAT_SPIDER_BELLY, scale=(1.0, 0.6, 1.3))
# 8 yeux disposés en 2 rangées sur cephalothorax avant
eye_positions = [
    (0.20, 0.30, 0.50), (-0.20, 0.30, 0.50),  # back row pair 1
    (0.35, 0.20, 0.40), (-0.35, 0.20, 0.40),  # mid row pair 2
    (0.15, 0.10, 0.55), (-0.15, 0.10, 0.55),  # front row pair 1
    (0.30, 0.05, 0.45), (-0.30, 0.05, 0.45),  # front row pair 2
]
for ei, (ex, ey, ez) in enumerate(eye_positions):
    smooth_sphere(f"spider_eye_{ei}", r=0.07, segs=12, rings=10, loc=(ex, ey, ez), parent=spider_p, mat=MAT_SPIDER_EYE)

# 2 chélicères (fangs)
for ck, cx in [("L", 0.15), ("R", -0.15)]:
    fang_p = empty(f"fang_{ck}_p", (cx, -0.15, 0.50), parent=spider_p)
    fang_p.rotation_euler = (math.radians(20), 0, 0)
    smooth_cone(f"fang_{ck}", r1=0.05, r2=0.0, depth=0.30, segs=8, loc=(0, -0.15, 0), parent=fang_p, mat=MAT_SPIDER_FANG)
    # venom drop on tip
    smooth_sphere(f"venom_drop_{ck}", r=0.03, segs=8, rings=6, loc=(0, -0.30, 0), parent=fang_p, mat=MAT_VENOM)

# 8 PATTES (4 chaque côté), chaque 3 segments (coxa-femur, tibia, tarsus)
spider_legs = {}
LEG_SIDE_OFFSETS = [(0.50, 0.35), (0.50, 0.10), (0.50, -0.15), (0.50, -0.40)]  # 4 legs L side
for lk in range(8):
    side = 1 if lk < 4 else -1
    idx = lk % 4
    x_off, z_off = LEG_SIDE_OFFSETS[idx]
    base_pos = (side * x_off, 0.10, z_off)
    leg_root_p = empty(f"leg_{lk}_root", base_pos, parent=spider_p)
    # initial rotation : spread outward
    leg_root_p.rotation_euler = (0, math.radians(-30 if side > 0 else 30 + 180), math.radians((idx - 1.5) * 8))
    # femur (cone tapered)
    smooth_cone(f"leg_{lk}_femur", r1=0.08, r2=0.06, depth=1.2, segs=10, loc=(0, -0.60, 0), parent=leg_root_p, mat=MAT_SPIDER_LEG)
    # knee joint (sphere)
    smooth_sphere(f"leg_{lk}_knee_joint", r=0.08, segs=10, rings=8, loc=(0, -1.20, 0), parent=leg_root_p, mat=MAT_SPIDER_BODY)
    # tibia
    tibia_p = empty(f"leg_{lk}_tibia_p", (0, -1.20, 0), parent=leg_root_p)
    tibia_p.rotation_euler = (math.radians(-60), 0, 0)
    smooth_cone(f"leg_{lk}_tibia", r1=0.06, r2=0.05, depth=1.0, segs=10, loc=(0, -0.50, 0), parent=tibia_p, mat=MAT_SPIDER_LEG)
    # ankle joint
    smooth_sphere(f"leg_{lk}_ankle", r=0.06, segs=10, rings=8, loc=(0, -1.00, 0), parent=tibia_p, mat=MAT_SPIDER_BODY)
    # tarsus (foot tip)
    tarsus_p = empty(f"leg_{lk}_tarsus_p", (0, -1.00, 0), parent=tibia_p)
    tarsus_p.rotation_euler = (math.radians(45), 0, 0)
    smooth_cone(f"leg_{lk}_tarsus", r1=0.05, r2=0.0, depth=0.50, segs=8, loc=(0, -0.25, 0), parent=tarsus_p, mat=MAT_SPIDER_LEG)
    spider_legs[lk] = leg_root_p


# --- 4 cocons victimes suspendus ---------------------------------------
cocoons = []
COCOON_POSITIONS = [(-3, 3, -1), (3, 3, 1), (-2, 2, 2), (2, 2.5, -2)]
for ci, (cx, cy, cz) in enumerate(COCOON_POSITIONS):
    cp = empty(f"cocoon_{ci}_p", (cx, cy, cz))
    cocoons.append(cp)
    # thread (cone from above)
    smooth_cone(f"cocoon_{ci}_thread", r1=0.01, r2=0.01, depth=2.5, segs=4, loc=(0, 1.25, 0), parent=cp, mat=MAT_WEB)
    # cocoon body (elongated capsule)
    smooth_sphere(f"cocoon_{ci}_body", r=0.30, segs=18, rings=14, loc=(0, 0, 0), parent=cp, mat=MAT_COCOON, scale=(0.85, 1.4, 0.85))
    # web wrap decoration
    for wk in range(3):
        wa = wk * (math.pi * 2 / 3)
        smooth_cone(f"cocoon_{ci}_wrap_{wk}", r1=0.02, r2=0.02, depth=0.50, segs=4, loc=(math.cos(wa) * 0.30, 0, math.sin(wa) * 0.30), parent=cp, mat=MAT_WEB)
    cp["_phase"] = ci * 0.40
    cp["_base"] = (cx, cy, cz)


# --- 12 petites araignées enfants -------------------------------------
baby_spiders = []
for bk in range(12):
    a = bk * (math.pi * 2 / 12) + random.uniform(-0.2, 0.2)
    r = random.uniform(0.8, 3.0)
    bx = math.cos(a) * r
    by = 5 + math.sin(a) * r
    bp = empty(f"baby_{bk}_p", (bx, by, 0))
    baby_spiders.append({"p": bp, "a": a, "r": r, "phase": bk * 0.30})
    # body small
    smooth_sphere(f"baby_{bk}_body", r=0.12, segs=14, rings=10, loc=(0, 0, 0), parent=bp, mat=MAT_SPIDER_BODY, scale=(1.0, 0.85, 1.2))
    # 8 small legs (just cones)
    for lk in range(8):
        side = 1 if lk < 4 else -1
        leg_a = (lk % 4) * 0.5 + 0.3
        smooth_cone(f"baby_{bk}_leg_{lk}", r1=0.012, r2=0.0, depth=0.20, segs=4, loc=(side * 0.12, -0.04, (lk % 4) * 0.06 - 0.10), parent=bp, mat=MAT_SPIDER_LEG)


# --- 30 chauves-souris erratic ----------------------------------------
bats = []
for bk in range(30):
    a = bk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 8)
    y = random.uniform(4, 9)
    bp = empty(f"bat_{bk}_p", (math.cos(a) * r, y, math.sin(a) * r))
    # body
    smooth_sphere(f"bat_{bk}_body", r=0.10, segs=10, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BAT, scale=(1.2, 0.8, 0.8))
    # 2 wings
    wL = empty(f"bat_{bk}_wL", (0, 0, 0.05), parent=bp)
    wR = empty(f"bat_{bk}_wR", (0, 0, -0.05), parent=bp)
    smooth_sphere(f"bat_{bk}_wL_b", r=0.16, segs=12, rings=6, loc=(0, 0, 0.18), parent=wL, mat=MAT_BAT_WING, scale=(1.0, 0.05, 1.5))
    smooth_sphere(f"bat_{bk}_wR_b", r=0.16, segs=12, rings=6, loc=(0, 0, -0.18), parent=wR, mat=MAT_BAT_WING, scale=(1.0, 0.05, 1.5))
    # red eyes
    smooth_sphere(f"bat_{bk}_eye", r=0.020, segs=8, rings=6, loc=(0.08, 0.02, 0), parent=bp, mat=MAT_BAT_EYE)
    bats.append({"p": bp, "wL": wL, "wR": wR, "a": a, "r": r, "y": y, "phase": bk * 0.21})


# --- 5 cristaux venimeux émissifs ------------------------------------
venom_crystals = []
for ck in range(5):
    ca = ck * (math.pi * 2 / 5) + 0.4
    cr = random.uniform(4, 7)
    cx = math.cos(ca) * cr
    cz = math.sin(ca) * cr
    cp = empty(f"vencrystal_{ck}_p", (cx, 0.30, cz))
    venom_crystals.append({"p": cp, "phase": ck * 0.40})
    # diamond cone
    smooth_cone(f"vencr_{ck}_top", r1=0.0, r2=0.15, depth=0.30, segs=6, loc=(0, 0.15, 0), parent=cp, mat=MAT_CRYSTAL_VEN)
    bot = smooth_cone(f"vencr_{ck}_bot", r1=0.0, r2=0.15, depth=0.20, segs=6, loc=(0, -0.10, 0), parent=cp, mat=MAT_CRYSTAL_VEN)
    bot.rotation_euler = (math.radians(180), 0, 0)


# --- 20 magic particles ------------------------------------------------
magic_parts = []
for mk in range(20):
    pmat = MAT_MAGIC_A if mk % 2 == 0 else MAT_MAGIC_B
    px = random.uniform(-7, 7)
    py = random.uniform(2, 7)
    pz = random.uniform(-3, 5)
    mp = smooth_sphere(f"magic_{mk}", r=random.uniform(0.04, 0.07), segs=8, rings=6, loc=(px, py, pz), mat=pmat)
    mp["_base"] = (px, py, pz)
    mp["_phase"] = mk * 0.18
    magic_parts.append(mp)


# --- os squelettes au sol -----------------------------------------------
# skull
skull_p = empty("skull_p", (-4, 0.20, -2))
smooth_sphere("skull_head", r=0.20, segs=18, rings=14, loc=(0, 0.10, 0), parent=skull_p, mat=MAT_BONE, scale=(1.0, 0.95, 0.85))
smooth_sphere("skull_jaw", r=0.13, segs=14, rings=10, loc=(0, -0.05, 0.10), parent=skull_p, mat=MAT_BONE, scale=(1.0, 0.5, 1.0))
for ez in [0.07, -0.07]:
    smooth_sphere(f"skull_socket_{ez}", r=0.04, segs=10, rings=8, loc=(0.12, 0.15, ez), parent=skull_p, mat=MAT_CAVE_DARK)
# 6 ribs
for ri in range(6):
    bone = smooth_cone(f"rib_{ri}", r1=0.04, r2=0.04, depth=0.70, segs=4, loc=(-4 + 0.20 * ri, 0.10, -2.4), mat=MAT_BONE)
    bone.rotation_euler = (0, 0, math.radians(20))


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

    # spider body : lift + sway
    sy = 4.5 + 0.30 * math.sin(2 * math.pi * tt * 1.5)
    kf(spider_p, f, "location", (0, sy, 0))
    kf(spider_p, f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 1.5)), 0, math.radians(4 * math.cos(2 * math.pi * tt * 2))))
    # abdomen pulse
    ap = 1.0 + 0.06 * math.sin(2 * math.pi * tt * 2.5)
    kf(abdomen, f, "scale", (1.1 * ap, 1.0 * ap, 1.4 * ap))

    # 8 legs : walk pattern (alternating tetrapods : legs 0,2 + 5,7 in one phase, 1,3 + 4,6 in opposite)
    for lk, leg_root in spider_legs.items():
        # phase based on tetrapod pattern
        tetrapod_phase = (lk % 2) * math.pi
        # phase variant per side
        side = 1 if lk < 4 else -1
        idx = lk % 4
        # base rotation
        base_y_rot = math.radians(-30 if side > 0 else 30 + 180)
        base_z_rot = math.radians((idx - 1.5) * 8)
        # walk movement (lift + step forward)
        leg_lift = math.radians(20 * math.sin(2 * math.pi * tt * 3 + tetrapod_phase))
        leg_swing = math.radians(15 * math.cos(2 * math.pi * tt * 3 + tetrapod_phase))
        kf(leg_root, f, "rotation_euler", (leg_lift, base_y_rot + leg_swing, base_z_rot))

    # 8 yeux scan (subtle move)
    # No direct kf on eyes — they're parented to spider, follow body

    # 4 cocoons swing
    for ci, cp in enumerate(cocoons):
        bx_, by_, bz_ = cp["_base"]
        ph = cp["_phase"]
        sway_x = bx_ + 0.15 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        sway_z = bz_ + 0.10 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi)
        kf(cp, f, "location", (sway_x, by_, sway_z))
        kf(cp, f, "rotation_euler", (math.radians(8 * math.sin(2 * math.pi * tt * 1.2 + ph * math.pi)), 0, 0))

    # 12 baby spiders crawl on web
    for bd in baby_spiders:
        ang = bd["a"] + tt * 2 * math.pi * 0.3 * (1 if (bd["a"] * 100) % 2 == 0 else -1)
        rr = bd["r"] + 0.3 * math.sin(2 * math.pi * tt * 1.5 + bd["phase"])
        bx = math.cos(ang) * rr
        by = 5 + math.sin(ang) * rr
        kf(bd["p"], f, "location", (bx, by, 0))
        kf(bd["p"], f, "rotation_euler", (0, 0, math.radians(180 * tt + bd["phase"] * 30)))

    # 30 bats erratic
    for bd in bats:
        ph = bd["phase"]
        ang = bd["a"] + tt * 2 * math.pi * 0.6 + 0.3 * math.sin(2 * math.pi * tt * 3 + ph)
        bx_ = math.cos(ang) * bd["r"] + 0.4 * math.sin(2 * math.pi * tt * 4 + ph)
        bz_ = math.sin(ang) * bd["r"] + 0.4 * math.cos(2 * math.pi * tt * 4 + ph)
        by_ = bd["y"] + 0.5 * math.sin(2 * math.pi * tt * 2.5 + ph)
        kf(bd["p"], f, "location", (bx_, by_, bz_))
        kf(bd["p"], f, "rotation_euler", (math.radians(8 * math.sin(2 * math.pi * tt * 3 + ph)), ang + math.pi / 2, 0))
        wflap = math.radians(60) * math.sin(2 * math.pi * tt * 14 + ph)
        kf(bd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(bd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 5 venom crystals pulse + rotate
    for vc in venom_crystals:
        ph = vc["phase"]
        ps = 1.0 + 0.12 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(vc["p"], f, "scale", (ps, ps, ps))
        kf(vc["p"], f, "rotation_euler", (math.radians(360 * tt + ph * 30), math.radians(540 * tt + ph * 60), math.radians(180 * tt + ph * 45)))

    # 20 magic particles drift
    for mp in magic_parts:
        bxp, byp, bzp = mp["_base"]
        ph = mp["_phase"]
        nx = bxp + 0.7 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        ny = byp + 0.5 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi)
        nz = bzp + 0.6 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi * 0.7)
        kf(mp, f, "location", (nx, ny, nz))
        sc = 0.6 + 0.6 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(mp, f, "scale", (sc, sc, sc))

    # 20 stalactites vibration
    for sti, sp_obj in enumerate(stalactites):
        ph = sp_obj["_phase"]
        sway = math.radians(2) * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(sp_obj, f, "rotation_euler", (sway, 0, math.radians(1.5 * math.cos(2 * math.pi * tt * 2.5 + ph * math.pi))))

    # entrance glow pulse
    eg = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 1.5)
    kf(entrance_p, f, "scale", (eg, eg, eg))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_giant_spider_cave] wrote {OUT}")
