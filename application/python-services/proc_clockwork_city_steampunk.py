"""
proc_clockwork_city_steampunk.py — 184e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Ville mécanique géante steampunk :
- 6 bâtiments avec engrenages géants visibles
- 12 engrenages rotatifs sur façades (rates couplés ratios)
- 8 tuyaux cuivre interconnectés
- 4 vapeurs émissives cheminées
- dirigeable hovering
- 12 lampes edison émissives
- 4 horloges murs avec aiguilles
- 8 ouvriers silhouettes
- ciel orange steampunk + soleil
- 8 nuages
- 30 sparks pulse

Animations multi-axes simultanées :
- 12 engrenages rotation rates différents
- 8 cheminées smoke rise cyclique
- dirigeable bob + propeller spin
- 12 lampes pulse différentielles
- 4 horloges aiguilles tournent
- 8 ouvriers walk slow
- 30 sparks parabolic
- nuages drift

Sortie : output/3d/pbr_clockcity_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_clockcity_proc.glb"))

random.seed(0xC10CC1)


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
MAT_SKY = make_mat("sky_steampunk", (0.85, 0.45, 0.25), roughness=1.0, emi=(0.65, 0.30, 0.18), emi_strength=1.0)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=12.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.85, 0.40), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.40), emi_strength=3.0)
MAT_CLOUD = make_mat("cloud", (0.85, 0.78, 0.70), roughness=1.0, alpha=0.65, emi=(0.40, 0.35, 0.30), emi_strength=0.4)
MAT_STONE = make_mat("stone", (0.45, 0.42, 0.38), roughness=0.85)
MAT_STONE_DARK = make_mat("stone_dark", (0.25, 0.22, 0.20), roughness=0.95)
MAT_BRICK = make_mat("brick", (0.55, 0.30, 0.20), roughness=0.85)
MAT_BRASS = make_mat("brass", (0.90, 0.70, 0.30), metallic=0.95, roughness=0.20, emi=(0.40, 0.30, 0.10), emi_strength=0.6)
MAT_BRASS_DARK = make_mat("brass_dark", (0.55, 0.40, 0.18), metallic=0.85, roughness=0.40)
MAT_COPPER = make_mat("copper", (0.85, 0.50, 0.30), metallic=0.85, roughness=0.30, emi=(0.30, 0.18, 0.12), emi_strength=0.4)
MAT_IRON = make_mat("iron", (0.30, 0.28, 0.28), metallic=0.80, roughness=0.50)
MAT_EDISON = make_mat("edison", (1.0, 0.65, 0.20), roughness=0.0, emi=(1.0, 0.65, 0.20), emi_strength=14.0)
MAT_BULB_GLASS = make_mat("bulb_glass", (1.0, 0.90, 0.65), roughness=0.10, alpha=0.45, emi=(1.0, 0.80, 0.40), emi_strength=2.0)
MAT_STEAM = make_mat("steam", (0.85, 0.78, 0.70), roughness=1.0, alpha=0.40, emi=(0.55, 0.50, 0.45), emi_strength=1.5)
MAT_CLOCK_FACE = make_mat("clock_face", (0.92, 0.85, 0.65), roughness=0.40, emi=(0.35, 0.30, 0.20), emi_strength=0.8)
MAT_DIRIGIBLE = make_mat("dirigible", (0.65, 0.55, 0.45), roughness=0.5, emi=(0.20, 0.18, 0.15), emi_strength=0.3)
MAT_WORKER = make_mat("worker", (0.30, 0.25, 0.20), roughness=0.7)
MAT_GROUND = make_mat("ground", (0.20, 0.15, 0.12), roughness=0.85)
MAT_SPARK = make_mat("spark", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)


# --- backdrop : steampunk sky ----------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 18, 12), mat=MAT_SKY)
ground = beveled_cube("ground", (40, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND)
sun_p = empty("sun_p", (10, 14, 8))
sun = smooth_sphere("sun", r=1.3, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.0, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=2.8, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# 8 clouds drift
clouds = []
for ck in range(8):
    cx = random.uniform(-15, 15)
    cy = random.uniform(11, 15)
    cz = random.uniform(5, 12)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    for j in range(3):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.7, 1.1), segs=14, rings=10, loc=(random.uniform(-0.9, 0.9), random.uniform(-0.2, 0.2), random.uniform(-0.6, 0.6)), parent=cp, mat=MAT_CLOUD, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.4, 0.8)


# --- 6 BÂTIMENTS avec engrenages géants -----------------------------
buildings = []
BUILD_POSITIONS = [(-9, 0, -2), (-3, 0, -2), (3, 0, -2), (9, 0, -2), (-6, 0, 4), (6, 0, 4)]
gears_on_buildings = []
for bi, (bx, by, bz) in enumerate(BUILD_POSITIONS):
    bp = empty(f"building_{bi}_p", (bx, by, bz))
    buildings.append(bp)
    bh = random.uniform(4.5, 7.0)
    bmat = MAT_STONE if bi % 2 == 0 else MAT_BRICK
    # main tower
    beveled_cube(f"building_{bi}_body", (2.2, bh, 1.8), bevel_offset=0.05, bevel_segments=2, loc=(0, bh / 2, 0), parent=bp, mat=bmat)
    # decorative bands copper
    for kk in range(3):
        ky = bh * 0.25 + kk * (bh * 0.25)
        smooth_cone(f"building_{bi}_band_{kk}", r1=1.20, r2=1.20, depth=0.06, segs=22, loc=(0, ky, 0), parent=bp, mat=MAT_COPPER)
    # roof (pointed)
    smooth_cone(f"building_{bi}_roof", r1=1.30, r2=0.10, depth=1.2, segs=10, loc=(0, bh + 0.6, 0), parent=bp, mat=MAT_STONE_DARK)
    # **2 engrenages géants sur façade**
    for gk in range(2):
        gy_off = bh * 0.35 + gk * (bh * 0.30)
        gr = 0.55
        gp = empty(f"gear_{bi}_{gk}_p", (0, gy_off, 1.0), parent=bp)
        # gear body
        gear_body = smooth_cone(f"gear_{bi}_{gk}_body", r1=gr, r2=gr, depth=0.10, segs=22, loc=(0, 0, 0), parent=gp, mat=MAT_BRASS)
        gear_body.rotation_euler = (math.radians(90), 0, 0)
        # teeth
        teeth = 12
        for tk in range(teeth):
            ta = tk * (math.pi * 2 / teeth)
            tooth_x = math.cos(ta) * (gr + 0.06)
            tooth_y = math.sin(ta) * (gr + 0.06)
            tooth = beveled_cube(f"gear_{bi}_{gk}_t_{tk}", (0.08, 0.10, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(tooth_x, tooth_y, 0), parent=gp, mat=MAT_BRASS_DARK)
            tooth.rotation_euler = (0, 0, ta)
        # center pin
        smooth_sphere(f"gear_{bi}_{gk}_pin", r=0.06, segs=12, rings=8, loc=(0, 0, 0), parent=gp, mat=MAT_BRASS)
        # 6 spokes
        for sk in range(6):
            sa = sk * (math.pi * 2 / 6)
            beveled_cube(f"gear_{bi}_{gk}_sp_{sk}", (0.04, gr * 0.85, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(math.cos(sa) * gr * 0.40, math.sin(sa) * gr * 0.40, 0), parent=gp, mat=MAT_BRASS_DARK)
            sp_obj = bpy.data.objects.get(f"gear_{bi}_{gk}_sp_{sk}")
            if sp_obj:
                sp_obj.rotation_euler = (0, 0, sa)
        # speed ratio coupling (each gear different speed)
        speed = (0.5 + (bi * 0.2) + (gk * 0.3)) * (1 if (bi * 2 + gk) % 2 == 0 else -1)
        gears_on_buildings.append({"p": gp, "speed": speed})

    # 1 horloge sur certains buildings
    if bi % 2 == 0:
        clock_p = empty(f"building_{bi}_clock_p", (0, bh - 1.5, 0.95), parent=bp)
        # frame
        smooth_cone(f"building_{bi}_clock_frame", r1=0.50, r2=0.50, depth=0.10, segs=22, loc=(0, 0, 0), parent=clock_p, mat=MAT_BRASS)
        # face
        smooth_cone(f"building_{bi}_clock_face_in", r1=0.42, r2=0.42, depth=0.05, segs=22, loc=(0, 0, 0.06), parent=clock_p, mat=MAT_CLOCK_FACE)
        # 12 numerals (small cubes)
        for n in range(12):
            na = -math.pi / 2 + n * (math.pi * 2 / 12)
            nx = math.cos(na) * 0.32
            ny = math.sin(na) * 0.32
            beveled_cube(f"building_{bi}_n_{n}", (0.04, 0.06, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(nx, ny, 0.09), parent=clock_p, mat=MAT_IRON)
        # hour hand
        hour_p = empty(f"building_{bi}_hour_p", (0, 0, 0.12), parent=clock_p)
        beveled_cube(f"building_{bi}_hour", (0.04, 0.22, 0.025), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.08, 0), parent=hour_p, mat=MAT_IRON)
        # minute hand
        minute_p = empty(f"building_{bi}_minute_p", (0, 0, 0.13), parent=clock_p)
        beveled_cube(f"building_{bi}_minute", (0.03, 0.36, 0.025), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.15, 0), parent=minute_p, mat=MAT_IRON)
        bp["_clock_hour"] = hour_p
        bp["_clock_minute"] = minute_p


# --- 4 CHEMINÉES vapeur ----------------------------------------------
chimneys = []
CHIM_POSITIONS = [(-9, 7.5, -2), (-3, 7.5, -2), (3, 7.5, -2), (9, 7.5, -2)]
for ci, (cx, cy, cz) in enumerate(CHIM_POSITIONS):
    chp = empty(f"chim_{ci}_p", (cx, cy, cz))
    chimneys.append(chp)
    # body
    smooth_cone(f"chim_{ci}_body", r1=0.22, r2=0.18, depth=1.5, segs=10, loc=(0, 0.75, 0), parent=chp, mat=MAT_IRON)
    # rim
    smooth_cone(f"chim_{ci}_rim", r1=0.25, r2=0.25, depth=0.06, segs=14, loc=(0, 1.50, 0), parent=chp, mat=MAT_COPPER)
    # 3 steam puffs
    steams = []
    for sk in range(3):
        sp = smooth_sphere(f"chim_{ci}_st_{sk}", r=0.30, segs=14, rings=10, loc=(0, 2.0 + sk * 0.55, 0), parent=chp, mat=MAT_STEAM, scale=(1.2, 1.0, 1.2))
        sp["_phase"] = sk * 0.33
        steams.append(sp)
    chimneys[ci] = {"p": chp, "steams": steams, "idx": ci}


# --- 8 TUYAUX CUIVRE interconnectés ------------------------------------
pipe_configs = [
    (-9, 4, -1.5, 6.0, 0),       # horizontal between buildings 0-1-2-3
    (-9, 3, 0, 1.0, 90),         # vertical short
    (0, 5, -1.5, 3.0, 0),        # mid horizontal
    (9, 4, -1.5, 1.5, 0),
    (-6, 2.5, -1, 1.5, 90),
    (6, 2.5, -1, 1.5, 90),
    (-3, 1.5, 1.5, 4.0, 0),
    (3, 1.5, 1.5, 4.0, 0),
]
for pi, (px, py, pz, plen, prot) in enumerate(pipe_configs):
    pipe = smooth_cone(f"pipe_{pi}", r1=0.10, r2=0.10, depth=plen, segs=10, loc=(px, py, pz), mat=MAT_COPPER)
    pipe.rotation_euler = (0, 0, math.radians(prot))
    # joints
    smooth_sphere(f"pipe_{pi}_joint_a", r=0.13, segs=14, rings=10, loc=(px - plen / 2 * math.cos(math.radians(prot)), py - plen / 2 * math.sin(math.radians(prot)), pz), mat=MAT_BRASS_DARK)
    smooth_sphere(f"pipe_{pi}_joint_b", r=0.13, segs=14, rings=10, loc=(px + plen / 2 * math.cos(math.radians(prot)), py + plen / 2 * math.sin(math.radians(prot)), pz), mat=MAT_BRASS_DARK)


# --- 12 LAMPES EDISON émissives ---------------------------------------
lamps = []
LAMP_POSITIONS = [
    (-9, 3, 1.0), (-3, 3, 1.0), (3, 3, 1.0), (9, 3, 1.0),
    (-9, 5, 1.0), (-3, 5, 1.0), (3, 5, 1.0), (9, 5, 1.0),
    (-6, 2, 5), (-2, 2, 5), (2, 2, 5), (6, 2, 5),
]
for li, (lx, ly, lz) in enumerate(LAMP_POSITIONS):
    lp = empty(f"lamp_{li}_p", (lx, ly, lz))
    lamps.append(lp)
    # bracket
    smooth_cone(f"lamp_{li}_bracket", r1=0.04, r2=0.03, depth=0.15, segs=6, loc=(0, 0, -0.10), parent=lp, mat=MAT_IRON)
    # glass
    smooth_sphere(f"lamp_{li}_glass", r=0.15, segs=14, rings=10, loc=(0, 0, 0), parent=lp, mat=MAT_BULB_GLASS, scale=(1.0, 1.3, 1.0))
    # filament glow
    fil = smooth_sphere(f"lamp_{li}_fil", r=0.07, segs=12, rings=8, loc=(0, 0, 0), parent=lp, mat=MAT_EDISON)
    lp["_phase"] = li * 0.20
    lp["_fil"] = fil


# --- DIRIGEABLE hovering ---------------------------------------------
dir_p = empty("dirigible", (0, 11, 2))
# envelope ovoide
smooth_sphere("dir_env", r=1.0, segs=24, rings=18, loc=(0, 0, 0), parent=dir_p, mat=MAT_DIRIGIBLE, scale=(2.5, 0.85, 0.85))
# 3 trim rings
for tb in range(3):
    tbx = -1.0 + tb * 1.0
    band = smooth_cone(f"dir_band_{tb}", r1=0.86, r2=0.86, depth=0.04, segs=22, loc=(tbx, 0, 0), parent=dir_p, mat=MAT_BRASS)
    band.rotation_euler = (0, math.radians(90), 0)
# gondola
beveled_cube("dir_gondola", (1.0, 0.30, 0.40), bevel_offset=0.04, bevel_segments=2, loc=(0, -0.80, 0), parent=dir_p, mat=MAT_COPPER)
# propeller back
prop_p = empty("dir_prop_p", (-2.0, 0, 0), parent=dir_p)
for pb in range(3):
    blade = beveled_cube(f"dir_prop_b_{pb}", (0.04, 0.45, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.20, 0), parent=prop_p, mat=MAT_BRASS_DARK)
    blade.rotation_euler = (0, math.radians(120 * pb), 0)
# small windows on gondola
for wk in range(4):
    wx = -0.4 + wk * 0.27
    smooth_sphere(f"dir_win_{wk}", r=0.06, segs=10, rings=6, loc=(wx, -0.80, 0.22), parent=dir_p, mat=MAT_EDISON, scale=(1.0, 1.0, 0.30))


# --- 8 OUVRIERS silhouettes -------------------------------------------
workers = []
for wk in range(8):
    a = wk * (math.pi * 2 / 8) + 0.3
    r = random.uniform(5, 9)
    wx = math.cos(a) * r
    wz = math.sin(a) * r * 0.5 + 1
    wp = empty(f"worker_{wk}_p", (wx, 0, wz))
    workers.append(wp)
    # body
    smooth_cone(f"worker_{wk}_b", r1=0.12, r2=0.17, depth=0.65, segs=8, loc=(0, 0.35, 0), parent=wp, mat=MAT_WORKER)
    # head
    smooth_sphere(f"worker_{wk}_h", r=0.10, segs=10, rings=8, loc=(0, 0.75, 0), parent=wp, mat=MAT_WORKER)
    # top hat (signature steampunk)
    smooth_cone(f"worker_{wk}_hat", r1=0.13, r2=0.10, depth=0.18, segs=10, loc=(0, 0.92, 0), parent=wp, mat=MAT_IRON)
    smooth_cone(f"worker_{wk}_hat_brim", r1=0.16, r2=0.16, depth=0.04, segs=12, loc=(0, 0.84, 0), parent=wp, mat=MAT_IRON)
    wp["_base_x"] = wx
    wp["_base_z"] = wz
    wp["_phase"] = wk * 0.20


# --- 30 SPARKS pulse cyclic ------------------------------------------
sparks = []
for sk in range(30):
    sx = random.uniform(-10, 10)
    sy = random.uniform(2, 7)
    sz = random.uniform(-3, 4)
    sp_obj = smooth_sphere(f"spark_{sk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(sx, sy, sz), mat=MAT_SPARK)
    sp_obj["_base"] = (sx, sy, sz)
    sp_obj["_phase"] = sk * 0.15
    sparks.append(sp_obj)


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

    # 12 GEARS rotation rates différents (ratios couplés)
    for gd in gears_on_buildings:
        ang = tt * 2 * math.pi * gd["speed"] * 2
        kf(gd["p"], f, "rotation_euler", (math.radians(90), 0, ang))

    # CHEMINÉES vapeur rise
    for ch in chimneys:
        if isinstance(ch, dict):
            for sp_st in ch["steams"]:
                ph = sp_st["_phase"]
                local = (tt * 1.5 + ph) % 1.0
                ny = 2.0 + local * 1.8
                sc = 1.0 + local * 1.0
                kf(sp_st, f, "location", (0, ny, 0))
                kf(sp_st, f, "scale", (sc, sc, sc))

    # DIRIGEABLE bob + propeller spin
    dx = 0 + 0.5 * math.sin(2 * math.pi * tt * 0.4)
    dy = 11 + 0.4 * math.cos(2 * math.pi * tt * 0.6)
    kf(dir_p, f, "location", (dx, dy, 2))
    kf(dir_p, f, "rotation_euler", (math.radians(3 * math.sin(2 * math.pi * tt * 1.2)), math.radians(20 * math.sin(2 * math.pi * tt * 0.3)), math.radians(2 * math.sin(2 * math.pi * tt * 1.0))))
    kf(prop_p, f, "rotation_euler", (math.radians(360 * tt * 8), 0, 0))

    # 12 LAMPS pulse
    for ld in lamps:
        ph = ld["_phase"]
        ps = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(ld["_fil"], f, "scale", (ps, ps, ps))

    # CLOCK hands (3 buildings have clocks)
    for bi in [0, 2, 4]:
        if bi < len(buildings):
            bp = buildings[bi]
            if "_clock_hour" in bp:
                hour_ang = tt * 2 * math.pi * 1.0
                minute_ang = tt * 2 * math.pi * 12.0
                kf(bp["_clock_hour"], f, "rotation_euler", (0, 0, -hour_ang))
                kf(bp["_clock_minute"], f, "rotation_euler", (0, 0, -minute_ang))

    # 8 WORKERS walk slow
    for wk_p in workers:
        bx_ = wk_p["_base_x"]
        bz_ = wk_p["_base_z"]
        ph = wk_p["_phase"]
        nx = bx_ + 0.5 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        nz = bz_ + 0.3 * math.cos(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(wk_p, f, "location", (nx, 0, nz))
        kf(wk_p, f, "rotation_euler", (0, math.radians(180 * tt + ph * 60), 0))

    # 30 SPARKS parabolic
    for sp_obj in sparks:
        bx_, by_, bz_ = sp_obj["_base"]
        ph = sp_obj["_phase"]
        local = (tt * 1.5 + ph) % 1.0
        ny = by_ + 4.0 * local * (1 - local)
        nx = bx_ + 0.3 * local
        nz = bz_ + 0.3 * local
        kf(sp_obj, f, "location", (nx, ny, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 5 + ph * math.pi))
        kf(sp_obj, f, "scale", (sc, sc, sc))

    # 8 clouds drift
    for cp in clouds:
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 5 - 2.5
        if new_x > 16:
            new_x -= 32
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))

    # sun pulse + halos breathe
    sp_sc = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sp_sc, sp_sc, sp_sc))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_clockwork_city_steampunk] wrote {OUT}")
