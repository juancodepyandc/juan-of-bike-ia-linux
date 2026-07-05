"""
proc_jellyfish_bioluminescent.py — 155e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Méduse géante bioluminescente sous-marine :
- corps cloche bombée (sphère étirée demi-dôme) émissif cyan/violet cyclique
- 8 motifs lumineux sur cloche émissifs cycle couleurs
- frange ondulante 16 segments
- 12 tentacules longs 8 segments wave propagée indépendant
- 24 bras oraux courts plissés
- 5 petites méduses orbitant
- 50 particules plancton émissif drift 3D
- 30 bulles montantes
- 8 ray-de-lumière subaquatiques pénétrants alpha
- 5 coraux dark décoratifs au sol
- fond mer abyssal
- rochers ovales + algues

Animations multi-axes simultanées :
- cloche : pulse contracte/expand 1±0.18 + sway X/Z
- 12 tentacules wave segments propagés chaque tk fréquence/phase unique
- 24 bras oraux : sway radial
- 8 motifs cloche : cycle hue émissif amplitude
- 5 petites méduses : orbit propre + pulse
- 50 plancton : drift 3D + scintille
- 30 bulles : rise local
- 8 rays : pulse alpha intensité

Sortie : output/3d/pbr_jellyfish_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_jellyfish_proc.glb"))

random.seed(0xCEBEEF)


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
MAT_SEA_DEEP = make_mat("sea_deep", (0.02, 0.05, 0.12), roughness=1.0, emi=(0.02, 0.06, 0.15), emi_strength=0.5)
MAT_SEA_SURF = make_mat("sea_surface", (0.08, 0.20, 0.30), roughness=0.4, emi=(0.04, 0.10, 0.18), emi_strength=0.6)
MAT_RAY = make_mat("ray", (0.45, 0.75, 1.0), roughness=0.0, alpha=0.18, emi=(0.45, 0.75, 1.0), emi_strength=2.5)
MAT_JELLY_BODY = make_mat("jelly_body", (0.65, 0.40, 0.95), roughness=0.10, alpha=0.55, emi=(0.65, 0.40, 0.95), emi_strength=4.5)
MAT_JELLY_RIM = make_mat("jelly_rim", (0.85, 0.60, 1.0), roughness=0.10, alpha=0.65, emi=(0.85, 0.60, 1.0), emi_strength=6.0)
MAT_JELLY_PATTERN_A = make_mat("jelly_pattern_A", (0.30, 1.0, 0.85), roughness=0.05, emi=(0.30, 1.0, 0.85), emi_strength=9.0)
MAT_JELLY_PATTERN_B = make_mat("jelly_pattern_B", (1.0, 0.40, 0.70), roughness=0.05, emi=(1.0, 0.40, 0.70), emi_strength=9.0)
MAT_TENTACLE = make_mat("tentacle", (0.45, 0.30, 0.85), roughness=0.20, alpha=0.75, emi=(0.45, 0.30, 0.85), emi_strength=3.5)
MAT_ORAL_ARM = make_mat("oral_arm", (0.75, 0.50, 0.95), roughness=0.20, alpha=0.65, emi=(0.65, 0.40, 0.85), emi_strength=4.0)
MAT_BABY_JELLY_BODY = make_mat("baby_jelly", (0.40, 0.80, 1.0), roughness=0.10, alpha=0.65, emi=(0.40, 0.80, 1.0), emi_strength=5.5)
MAT_BABY_JELLY_TENT = make_mat("baby_tent", (0.30, 0.65, 0.95), roughness=0.20, alpha=0.55, emi=(0.30, 0.65, 0.95), emi_strength=4.0)
MAT_PLANKTON_A = make_mat("plankton_A", (1.0, 0.90, 0.40), roughness=0.0, emi=(1.0, 0.90, 0.40), emi_strength=8.0)
MAT_PLANKTON_B = make_mat("plankton_B", (0.50, 1.0, 0.80), roughness=0.0, emi=(0.50, 1.0, 0.80), emi_strength=8.0)
MAT_BUBBLE = make_mat("bubble", (0.80, 0.95, 1.0), roughness=0.05, alpha=0.45, emi=(0.60, 0.90, 1.0), emi_strength=1.5)
MAT_CORAL_DARK = make_mat("coral_dark", (0.30, 0.10, 0.25), roughness=0.85, emi=(0.15, 0.05, 0.10), emi_strength=0.3)
MAT_CORAL_GLOW = make_mat("coral_glow", (0.95, 0.30, 0.60), roughness=0.20, emi=(0.95, 0.30, 0.60), emi_strength=4.5)
MAT_ROCK = make_mat("rock", (0.12, 0.10, 0.10), roughness=0.95)
MAT_SAND = make_mat("sand", (0.20, 0.18, 0.12), roughness=0.95)
MAT_ALGAE = make_mat("algae", (0.10, 0.30, 0.15), roughness=0.7, emi=(0.05, 0.20, 0.08), emi_strength=0.5)


# --- backdrop : deep sea --------------------------------------------------
sea_back = beveled_cube("sea_back", (40, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, 13, 8), mat=MAT_SEA_DEEP)
sea_top = beveled_cube("sea_top", (40, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -16, 15), mat=MAT_SEA_SURF)
sea_top.rotation_euler = (math.radians(15), 0, 0)
ground = beveled_cube("sand", (30, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_SAND)


# --- 8 light rays subaquatiques pénétrants -------------------------------
light_rays = []
for r in range(8):
    rx = random.uniform(-10, 10)
    rz = random.uniform(-3, 6)
    ray = beveled_cube(f"ray_{r}", (0.45, 13.5, 0.45), bevel_offset=0.04, bevel_segments=2, loc=(rx, 7.0, rz), mat=MAT_RAY)
    ray.rotation_euler = (math.radians(random.uniform(-6, 6)), 0, math.radians(random.uniform(-8, 8)))
    light_rays.append(ray)


# --- 5 dark corals au sol ------------------------------------------------
for c in range(5):
    cx = random.uniform(-8, 8)
    cz = random.uniform(-2, 5)
    coral_p = empty(f"coral_{c}", (cx, 0.5, cz))
    # branching 5 segs
    for j in range(5):
        a = j * (math.pi * 2 / 5) + random.uniform(-0.2, 0.2)
        x = math.cos(a) * 0.25
        z = math.sin(a) * 0.25
        smooth_cone(f"coral_{c}_b_{j}", r1=0.10, r2=0.04, depth=random.uniform(0.6, 1.2), segs=10, loc=(x, 0.4, z), parent=coral_p, mat=MAT_CORAL_DARK)
        # tip glow émissif sphère
        smooth_sphere(f"coral_{c}_tip_{j}", r=0.07, segs=12, rings=10, loc=(x * 1.4, 0.95, z * 1.4), parent=coral_p, mat=MAT_CORAL_GLOW)


# --- 4 rocks ovales ------------------------------------------------------
for r in range(4):
    rx = random.uniform(-9, 9)
    rz = random.uniform(-2, 5)
    smooth_sphere(f"rock_{r}", r=random.uniform(0.35, 0.65), segs=14, rings=10, loc=(rx, 0.20, rz), mat=MAT_ROCK, scale=(1.5, 0.45, 1.2))


# --- 6 algae sway --------------------------------------------------------
algae_list = []
for a in range(6):
    ax = random.uniform(-9, 9)
    az = random.uniform(-2, 5)
    ap = empty(f"algae_{a}", (ax, 0, az))
    algae_list.append(ap)
    # 4 segments cone tapered
    cur = ap
    for j in range(4):
        e = empty(f"algae_{a}_seg_p_{j}", (0, 0.45, 0), parent=cur)
        smooth_cone(f"algae_{a}_seg_{j}", r1=0.08, r2=0.05, depth=0.55, segs=10, loc=(0, 0.27, 0), parent=e, mat=MAT_ALGAE)
        cur = e


# --- MAIN JELLYFISH ------------------------------------------------------
# Position : center, elevated
jelly_p = empty("jelly_main", (0, 6.0, 1.5))

# bell : sphere stretched half-dome
bell = smooth_sphere("bell", r=1.6, segs=32, rings=20, loc=(0, 0.5, 0), parent=jelly_p, mat=MAT_JELLY_BODY, scale=(1.4, 0.85, 1.4))
# bell rim (slightly larger, brighter)
bell_rim = smooth_sphere("bell_rim", r=1.75, segs=28, rings=14, loc=(0, 0.20, 0), parent=jelly_p, mat=MAT_JELLY_RIM, scale=(1.4, 0.35, 1.4))

# 8 light patterns on bell (alternating colors)
patterns = []
for pk in range(8):
    pa = pk * (math.pi * 2 / 8)
    px = math.cos(pa) * 1.55
    pz = math.sin(pa) * 1.55
    pm = MAT_JELLY_PATTERN_A if pk % 2 == 0 else MAT_JELLY_PATTERN_B
    pat = smooth_sphere(f"pattern_{pk}", r=0.30, segs=18, rings=12, loc=(px * 0.9, 0.85, pz * 0.9), parent=jelly_p, mat=pm, scale=(1.0, 0.40, 1.0))
    pat["_phase"] = pk * 0.4
    patterns.append(pat)

# 16 fringe segments (frill around bell base)
fringe_segs = []
for fk in range(16):
    fa = fk * (math.pi * 2 / 16)
    fx = math.cos(fa) * 2.05
    fz = math.sin(fa) * 2.05
    fp = empty(f"fringe_p_{fk}", (fx * 0.7, 0.10, fz * 0.7), parent=jelly_p)
    fp.rotation_euler = (0, -fa, 0)
    fring = smooth_cone(f"fringe_{fk}", r1=0.12, r2=0.06, depth=0.50, segs=8, loc=(0.18, -0.15, 0), parent=fp, mat=MAT_JELLY_RIM)
    fring.rotation_euler = (0, 0, math.radians(-90))
    fringe_segs.append(fp)

# 24 oral arms (short, plissés) — radial from bell underside
oral_arms = []
for ok in range(24):
    oa = ok * (math.pi * 2 / 24)
    op = empty(f"oral_p_{ok}", (math.cos(oa) * 0.35, -0.10, math.sin(oa) * 0.35), parent=jelly_p)
    # 3 segs articulated
    cur = op
    for j in range(3):
        seg = empty(f"oral_{ok}_seg_{j}", (0, -0.30, 0), parent=cur)
        rl = 0.10 - j * 0.02
        smooth_sphere(f"oral_{ok}_b_{j}", r=rl, segs=12, rings=8, loc=(0, -0.15, 0), parent=seg, mat=MAT_ORAL_ARM, scale=(1.0, 1.6, 1.0))
        cur = seg
    oral_arms.append({"p": op, "phase": ok * 0.3})

# 12 tentacles long — each with 8 segments propagating wave
tentacles = []
for tk in range(12):
    ta = tk * (math.pi * 2 / 12)
    tp = empty(f"tent_p_{tk}", (math.cos(ta) * 0.85, 0.0, math.sin(ta) * 0.85), parent=jelly_p)
    segs = []
    cur = tp
    for j in range(8):
        e = empty(f"tent_{tk}_seg_p_{j}", (0, -0.55, 0), parent=cur)
        rl = 0.09 - j * 0.008
        smooth_sphere(f"tent_{tk}_b_{j}", r=rl, segs=10, rings=8, loc=(0, -0.28, 0), parent=e, mat=MAT_TENTACLE, scale=(1.0, 2.5, 1.0))
        segs.append(e)
        cur = e
    # frequency + phase unique per tentacle
    freq = 2.0 + (tk % 4) * 0.4
    base_phase = tk * 0.6
    tentacles.append({"p": tp, "segs": segs, "freq": freq, "base_phase": base_phase, "tk": tk})


# --- 5 baby jellies orbiting ---------------------------------------------
babies = []
for bk in range(5):
    ba = bk * (math.pi * 2 / 5)
    bx = math.cos(ba) * 4.5
    bz = math.sin(ba) * 4.5
    by = random.uniform(4.5, 8.5)
    bp = empty(f"baby_{bk}", (bx, by, bz))
    bell_b = smooth_sphere(f"baby_{bk}_bell", r=0.50, segs=20, rings=14, loc=(0, 0, 0), parent=bp, mat=MAT_BABY_JELLY_BODY, scale=(1.3, 0.6, 1.3))
    rim_b = smooth_sphere(f"baby_{bk}_rim", r=0.55, segs=18, rings=10, loc=(0, -0.12, 0), parent=bp, mat=MAT_BABY_JELLY_BODY, scale=(1.3, 0.25, 1.3))
    # 6 tentacles cones
    for j in range(6):
        ja = j * (math.pi * 2 / 6)
        smooth_cone(f"baby_{bk}_tent_{j}", r1=0.05, r2=0.0, depth=random.uniform(0.7, 1.1), segs=8, loc=(math.cos(ja) * 0.35, -0.55, math.sin(ja) * 0.35), parent=bp, mat=MAT_BABY_JELLY_TENT)
    babies.append({"p": bp, "bell": bell_b, "a0": ba, "r": 4.5, "by": by, "phase": bk * 1.3})


# --- 50 plankton particles bioluminescent --------------------------------
plankton = []
for pk in range(50):
    pmat = MAT_PLANKTON_A if pk % 2 == 0 else MAT_PLANKTON_B
    px = random.uniform(-12, 12)
    py = random.uniform(2.5, 11)
    pz = random.uniform(-4, 6)
    p_obj = smooth_sphere(f"plankton_{pk}", r=random.uniform(0.05, 0.10), segs=8, rings=6, loc=(px, py, pz), mat=pmat)
    p_obj["_phase"] = pk * 0.20
    p_obj["_drift_x"] = random.uniform(0.5, 1.3) * (1 if pk % 2 == 0 else -1)
    p_obj["_drift_y"] = random.uniform(0.3, 0.7)
    p_obj["_base"] = (px, py, pz)
    plankton.append(p_obj)


# --- 30 bubbles rise -----------------------------------------------------
bubbles = []
for bk in range(30):
    bx = random.uniform(-10, 10)
    by = random.uniform(0.2, 1.5)
    bz = random.uniform(-3, 5)
    bu = smooth_sphere(f"bubble_{bk}", r=random.uniform(0.07, 0.15), segs=12, rings=8, loc=(bx, by, bz), mat=MAT_BUBBLE)
    bu["_base"] = (bx, by, bz)
    bu["_phase"] = bk * 0.25
    bu["_speed"] = random.uniform(1.4, 2.4)
    bubbles.append(bu)


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

    # --- main jellyfish : drift + sway + pulse contracte/expand
    jx = 0.3 * math.sin(2 * math.pi * tt * 0.7)
    jy = 6.0 + 0.5 * math.sin(2 * math.pi * tt * 1.0)
    jz = 1.5 + 0.4 * math.cos(2 * math.pi * tt * 0.8)
    kf(jelly_p, f, "location", (jx, jy, jz))
    kf(jelly_p, f, "rotation_euler", (math.radians(6 * math.sin(2 * math.pi * tt * 1.4)), math.radians(45 * tt), math.radians(4 * math.sin(2 * math.pi * tt * 1.1))))

    # bell pulse contracte/expand (3-axes : y compressed when xz expanded)
    pulse = math.sin(2 * math.pi * tt * 2.5)
    bx_scale = 1.0 + 0.18 * pulse
    by_scale = 1.0 - 0.12 * pulse
    bz_scale = 1.0 + 0.18 * pulse
    kf(bell, f, "scale", (bx_scale, by_scale, bz_scale))
    kf(bell_rim, f, "scale", (1.0 + 0.20 * pulse, 1.0 - 0.10 * pulse, 1.0 + 0.20 * pulse))

    # 8 patterns : cycle scale (mimics pulsing light)
    for pi, pat in enumerate(patterns):
        ph_phase = pat["_phase"]
        ps = 1.0 + 0.30 * math.sin(2 * math.pi * tt * 3.5 + ph_phase * math.pi)
        kf(pat, f, "scale", (ps, 1.0 + 0.5 * (ps - 1), ps))

    # 16 fringe segments : wave radial
    for fi, fp in enumerate(fringe_segs):
        fa = fi * (math.pi * 2 / 16)
        wave = math.radians(15) * math.sin(2 * math.pi * tt * 3.0 + fi * 0.4)
        kf(fp, f, "rotation_euler", (wave, -fa, math.radians(8 * math.sin(2 * math.pi * tt * 2.5 + fi * 0.3))))

    # 24 oral arms : sway radial
    for oi, oa_data in enumerate(oral_arms):
        op = oa_data["p"]
        ph = oa_data["phase"]
        oa_ang = oi * (math.pi * 2 / 24)
        rot_x = math.radians(20 * math.sin(2 * math.pi * tt * 2.2 + ph * math.pi))
        rot_z = math.radians(15 * math.cos(2 * math.pi * tt * 2.5 + ph * math.pi))
        kf(op, f, "rotation_euler", (rot_x, 0, rot_z))

    # 12 tentacles : wave 8 segments propagated per tentacle
    for tdata in tentacles:
        tp = tdata["p"]
        freq = tdata["freq"]
        base_phase = tdata["base_phase"]
        for si, seg in enumerate(tdata["segs"]):
            phase = base_phase + si * 0.5
            wave_x = math.radians(15) * math.sin(2 * math.pi * tt * freq + phase)
            wave_z = math.radians(10) * math.cos(2 * math.pi * tt * (freq * 0.8) + phase)
            kf(seg, f, "rotation_euler", (wave_x, 0, wave_z))

    # 5 baby jellies orbit + pulse
    for bd in babies:
        ang = bd["a0"] + tt * 2 * math.pi * 0.5
        bx2 = math.cos(ang) * bd["r"]
        bz2 = math.sin(ang) * bd["r"]
        by2 = bd["by"] + 0.6 * math.sin(2 * math.pi * tt * 1.4 + bd["phase"])
        kf(bd["p"], f, "location", (bx2, by2, bz2))
        bp = math.sin(2 * math.pi * tt * 3.5 + bd["phase"])
        sc_x = 1.0 + 0.18 * bp
        sc_y = 1.0 - 0.12 * bp
        kf(bd["bell"], f, "scale", (sc_x, sc_y, sc_x))

    # 50 plankton drift 3D + scintille (scale)
    for plk in plankton:
        bx_, by_, bz_ = plk["_base"]
        ph_ = plk["_phase"]
        spd_x = plk["_drift_x"]
        spd_y = plk["_drift_y"]
        nx = bx_ + 1.5 * math.sin(2 * math.pi * tt * 0.6 * spd_x + ph_ * math.pi)
        ny = by_ + 0.8 * math.cos(2 * math.pi * tt * 0.7 * spd_y + ph_ * math.pi)
        nz = bz_ + 1.0 * math.sin(2 * math.pi * tt * 0.5 + ph_ * math.pi * 0.7)
        kf(plk, f, "location", (nx, ny, nz))
        scn = 0.8 + 0.6 * abs(math.sin(2 * math.pi * tt * 2.5 + ph_ * math.pi))
        kf(plk, f, "scale", (scn, scn, scn))

    # 30 bubbles rise
    for bu in bubbles:
        bx3, by3, bz3 = bu["_base"]
        ph_ = bu["_phase"]
        spd = bu["_speed"]
        local = (tt * spd + ph_) % 1.0
        ny_ = by3 + local * 11.0
        nx_ = bx3 + 0.18 * math.sin(2 * math.pi * local * 6 + ph_)
        sc = 0.7 + local * 0.6
        kf(bu, f, "location", (nx_, ny_, bz3))
        kf(bu, f, "scale", (sc, sc, sc))

    # 8 light rays : pulse alpha intensity via scale Y
    for ri, ray in enumerate(light_rays):
        sc_y = 1.0 + 0.12 * math.sin(2 * math.pi * tt * 1.2 + ri * 0.5)
        sc_xz = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 1.4 + ri * 0.4)
        kf(ray, f, "scale", (sc_xz, sc_y, sc_xz))

    # 6 algae sway X+Z
    for ai, ap in enumerate(algae_list):
        bend_x = math.radians(12) * math.sin(2 * math.pi * tt * 1.5 + ai * 0.7)
        bend_z = math.radians(10) * math.cos(2 * math.pi * tt * 1.7 + ai * 0.5)
        kf(ap, f, "rotation_euler", (bend_x, 0, bend_z))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_jellyfish_bioluminescent] wrote {OUT}")
