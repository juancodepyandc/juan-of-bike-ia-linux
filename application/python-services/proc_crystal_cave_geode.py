"""
proc_crystal_cave_geode.py — 161e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Caverne cristal avec géode éclatée révélant 100 cristaux multicolores :
- voûte caverne (sphère grosses rocks bevelés)
- 30 stalactites pendant
- 25 stalagmites montant
- geode central éclatée révélant 100 cristaux émissifs radiaux
- bassin d'eau souterrain émissif
- 8 cristaux flottants extérieurs orbitant
- 6 champignons bioluminescents
- 12 chauves-souris volant
- 50 particules magic drift 3D
- 5 cristaux pendants suspendus
- entrée caverne lumineuse arrière-plan

Animations multi-axes simultanées :
- 100 cristaux geode : vague de pulse émission propagée du centre (couleurs cyclent radial)
- 30 stalactites : vibration légère
- 8 cristaux flottants : orbit + rotate XYZ + pulse
- 12 chauves-souris : flap + dart erratic
- 50 particules : drift 3D + scintille
- bassin : rippling waves (10 segs)
- 6 champignons pulse émission
- 5 cristaux pendants sway

Sortie : output/3d/pbr_crystalcave_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_crystalcave_proc.glb"))

random.seed(0xCEC10D)


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
MAT_CAVE_DARK = make_mat("cave_dark", (0.06, 0.05, 0.08), roughness=1.0, emi=(0.04, 0.04, 0.08), emi_strength=0.4)
MAT_ROCK_A = make_mat("rock_A", (0.20, 0.18, 0.22), roughness=0.95)
MAT_ROCK_B = make_mat("rock_B", (0.30, 0.25, 0.28), roughness=0.95)
MAT_STALAC = make_mat("stalactite", (0.45, 0.40, 0.50), roughness=0.85, emi=(0.15, 0.12, 0.18), emi_strength=0.5)
MAT_GEODE_SHELL = make_mat("geode_shell", (0.30, 0.25, 0.30), roughness=0.85, emi=(0.10, 0.08, 0.12), emi_strength=0.4)
MAT_C_PURPLE = make_mat("c_purple", (0.70, 0.30, 0.95), roughness=0.05, emi=(0.70, 0.30, 0.95), emi_strength=12.0)
MAT_C_CYAN = make_mat("c_cyan", (0.30, 0.85, 0.95), roughness=0.05, emi=(0.30, 0.85, 0.95), emi_strength=12.0)
MAT_C_GREEN = make_mat("c_green", (0.30, 0.95, 0.50), roughness=0.05, emi=(0.30, 0.95, 0.50), emi_strength=12.0)
MAT_C_BLUE = make_mat("c_blue", (0.20, 0.40, 0.95), roughness=0.05, emi=(0.20, 0.40, 0.95), emi_strength=12.0)
MAT_C_RED = make_mat("c_red", (0.95, 0.30, 0.40), roughness=0.05, emi=(0.95, 0.30, 0.40), emi_strength=12.0)
MAT_C_YELLOW = make_mat("c_yellow", (0.95, 0.85, 0.20), roughness=0.05, emi=(0.95, 0.85, 0.20), emi_strength=12.0)
MAT_C_PINK = make_mat("c_pink", (1.0, 0.45, 0.85), roughness=0.05, emi=(1.0, 0.45, 0.85), emi_strength=12.0)
MAT_C_TURQ = make_mat("c_turq", (0.30, 1.0, 0.85), roughness=0.05, emi=(0.30, 1.0, 0.85), emi_strength=12.0)
MAT_WATER = make_mat("water", (0.30, 0.55, 0.85), roughness=0.10, alpha=0.65, emi=(0.20, 0.45, 0.75), emi_strength=2.5)
MAT_MUSH_STEM = make_mat("mush_stem", (0.65, 0.55, 0.40), roughness=0.6)
MAT_MUSH_CAP = make_mat("mush_cap", (0.45, 0.85, 0.95), roughness=0.4, emi=(0.45, 0.85, 0.95), emi_strength=7.0)
MAT_MUSH_CAP2 = make_mat("mush_cap2", (0.95, 0.50, 0.85), roughness=0.4, emi=(0.95, 0.50, 0.85), emi_strength=7.0)
MAT_BAT = make_mat("bat", (0.10, 0.08, 0.08), roughness=0.7)
MAT_BAT_WING = make_mat("bat_wing", (0.15, 0.10, 0.10), roughness=0.6, alpha=0.85)
MAT_MAGIC_A = make_mat("magic_A", (0.85, 0.55, 1.0), roughness=0.0, emi=(0.85, 0.55, 1.0), emi_strength=8.0)
MAT_MAGIC_B = make_mat("magic_B", (0.55, 0.95, 1.0), roughness=0.0, emi=(0.55, 0.95, 1.0), emi_strength=8.0)
MAT_ENTRANCE_LIGHT = make_mat("entrance_light", (0.85, 0.65, 0.40), roughness=0.0, emi=(0.85, 0.65, 0.40), emi_strength=4.0)


# --- backdrop : dark cave + entrance light ---------------------------------
sky_back = beveled_cube("cave_back", (40, 0.2, 20), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 10), mat=MAT_CAVE_DARK)
floor = beveled_cube("floor", (28, 0.2, 18), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_ROCK_A)

# entrance light arrière-plan (cave opening)
entrance_p = empty("entrance_p", (0, 5, 9))
smooth_sphere("entrance_glow", r=2.5, segs=22, rings=14, loc=(0, 0, 0), parent=entrance_p, mat=MAT_ENTRANCE_LIGHT, scale=(1.3, 0.85, 0.30))


# --- cavern vault (dome of rocks) ----------------------------------------
vault_p = empty("vault_p", (0, 0, 0))
# 40 big rocks distributed dome shape
for rk in range(40):
    # spherical distribution but only top hemisphere
    theta = random.uniform(0, math.pi / 2.2)  # 0 to ~80°
    phi = random.uniform(0, math.pi * 2)
    R = random.uniform(11, 13)
    x = R * math.sin(theta) * math.cos(phi)
    y = R * math.cos(theta) + 2  # offset up
    z = R * math.sin(theta) * math.sin(phi)
    rmat = MAT_ROCK_A if rk % 2 == 0 else MAT_ROCK_B
    smooth_sphere(f"vault_rock_{rk}", r=random.uniform(0.8, 1.6), segs=14, rings=10, loc=(x, y, z), parent=vault_p, mat=rmat, scale=(1.0, 0.85, 1.0))


# --- 30 stalactites pending from vault -----------------------------------
stalactites = []
for sk in range(30):
    a = random.uniform(0, math.pi * 2)
    r = random.uniform(0.5, 9.0)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    sy = random.uniform(7, 11)
    sh = random.uniform(0.6, 1.8)
    stal_p = empty(f"stal_{sk}_p", (sx, sy, sz))
    stalactites.append(stal_p)
    # pointing down (inverted cone)
    stal = smooth_cone(f"stal_{sk}", r1=0.20, r2=0.0, depth=sh, segs=10, loc=(0, -sh / 2, 0), parent=stal_p, mat=MAT_STALAC)
    # 3 tiny crystals attached at tip
    for tc in range(3):
        ta = tc * (math.pi * 2 / 3)
        cmat = [MAT_C_PURPLE, MAT_C_CYAN, MAT_C_PINK][tc]
        smooth_cone(f"stal_{sk}_c_{tc}", r1=0.0, r2=0.04, depth=0.10, segs=6, loc=(math.cos(ta) * 0.05, -sh - 0.08, math.sin(ta) * 0.05), parent=stal_p, mat=cmat)
    stal_p["_phase"] = sk * 0.20


# --- 25 stalagmites montant du sol ---------------------------------------
for sk in range(25):
    a = random.uniform(0, math.pi * 2)
    r = random.uniform(0.5, 8.0)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    # avoid central geode area
    if abs(sx) < 2.5 and abs(sz) < 2.5:
        continue
    sh = random.uniform(0.5, 1.5)
    sg = smooth_cone(f"stalg_{sk}", r1=0.20, r2=0.0, depth=sh, segs=10, loc=(sx, sh / 2, sz), mat=MAT_STALAC)
    # cap with small crystals
    for tc in range(2):
        ta = tc * math.pi + random.uniform(0, 0.5)
        cmat = [MAT_C_GREEN, MAT_C_BLUE, MAT_C_YELLOW, MAT_C_TURQ][tc % 4]
        smooth_cone(f"stalg_{sk}_c_{tc}", r1=0.0, r2=0.05, depth=0.12, segs=6, loc=(sx + math.cos(ta) * 0.05, sh + 0.06, sz + math.sin(ta) * 0.05), mat=cmat)


# --- CENTRAL GEODE éclatée révélant 100 cristaux --------------------------
geode_p = empty("geode_p", (0, 0.5, 0))
# 2 half-shells (geode broken open)
for sk in [0, 1]:
    shell_p = empty(f"geode_shell_p_{sk}", (0, 0, 0), parent=geode_p)
    shell_p.rotation_euler = (0, sk * math.pi, 0)
    # half-sphere shell (using flatten sphere)
    shell = smooth_sphere(f"geode_shell_{sk}", r=2.0, segs=24, rings=18, loc=(-1.0, 1.0, 0), parent=shell_p, mat=MAT_GEODE_SHELL, scale=(0.7, 0.95, 1.5))
    shell.rotation_euler = (0, 0, math.radians(15 if sk == 0 else -15))

# 100 cristaux émissifs en grappe radiale (hemisphere upward facing)
crystal_mats = [MAT_C_PURPLE, MAT_C_CYAN, MAT_C_GREEN, MAT_C_BLUE, MAT_C_RED, MAT_C_YELLOW, MAT_C_PINK, MAT_C_TURQ]
geode_crystals = []
for ck in range(100):
    # spherical distribution (upper hemisphere)
    theta = random.uniform(0, math.pi / 2.5)
    phi = random.uniform(0, math.pi * 2)
    R = random.uniform(0.3, 1.7)
    cx = R * math.sin(theta) * math.cos(phi)
    cy = R * math.cos(theta) + 0.8
    cz = R * math.sin(theta) * math.sin(phi)
    cmat = crystal_mats[ck % 8]
    cp = empty(f"crystal_{ck}_p", (cx, cy, cz), parent=geode_p)
    # cone pointing outward (radial direction)
    radial_dir = (cx, cy - 0.8, cz)
    rd_len = math.sqrt(radial_dir[0]**2 + radial_dir[1]**2 + radial_dir[2]**2)
    if rd_len > 0:
        # angle to align Z axis with radial
        yaw = math.atan2(radial_dir[2], radial_dir[0])
        pitch = math.atan2(radial_dir[1], math.sqrt(radial_dir[0]**2 + radial_dir[2]**2))
        cp.rotation_euler = (-pitch, -yaw, 0)
    crystal_h = random.uniform(0.20, 0.45)
    crystal_r = random.uniform(0.05, 0.12)
    smooth_cone(f"crystal_{ck}_top", r1=0.0, r2=crystal_r, depth=crystal_h, segs=6, loc=(0, 0, 0), parent=cp, mat=cmat)
    geode_crystals.append({"p": cp, "radial_dist": rd_len, "phase": ck * 0.10, "color_idx": ck % 8})


# --- bassin d'eau souterrain (poolside) ----------------------------------
pool_p = empty("pool_p", (5, 0, -2))
# pool surface (flat circular)
pool = smooth_cone("pool", r1=1.8, r2=1.8, depth=0.10, segs=22, loc=(0, 0.05, 0), parent=pool_p, mat=MAT_WATER)
# 10 ripple segments (concentric)
ripples = []
for rk in range(10):
    ra = rk * (math.pi * 2 / 10)
    rr = 0.5 + (rk % 3) * 0.4
    rip = smooth_cone(f"ripple_{rk}", r1=rr, r2=rr * 1.05, depth=0.04, segs=18, loc=(0, 0.10, 0), parent=pool_p, mat=MAT_WATER)
    rip["_phase"] = rk * 0.30
    rip["_base_r"] = rr
    ripples.append(rip)


# --- 8 cristaux flottants extérieurs orbitant ---------------------------
floating_crystals = []
for fk in range(8):
    fa = fk * (math.pi * 2 / 8)
    fr = random.uniform(4, 7)
    fx = math.cos(fa) * fr
    fy = random.uniform(3, 7)
    fz = math.sin(fa) * fr
    fcp = empty(f"fcrystal_{fk}_p", (fx, fy, fz))
    cmat = crystal_mats[fk]
    # diamond (cone top + bottom)
    smooth_cone(f"fcrystal_{fk}_top", r1=0.0, r2=0.18, depth=0.30, segs=6, loc=(0, 0.15, 0), parent=fcp, mat=cmat)
    bot = smooth_cone(f"fcrystal_{fk}_bot", r1=0.0, r2=0.18, depth=0.25, segs=6, loc=(0, -0.13, 0), parent=fcp, mat=cmat)
    bot.rotation_euler = (math.radians(180), 0, 0)
    floating_crystals.append({"p": fcp, "a": fa, "r": fr, "y0": fy, "phase": fk * 0.5})


# --- 6 champignons bioluminescents ---------------------------------------
mushrooms = []
for mk in range(6):
    mx = random.uniform(-8, 8)
    mz = random.uniform(-3, 6)
    if abs(mx) < 2.5 and abs(mz) < 2.5:
        continue
    mp = empty(f"mush_{mk}", (mx, 0.05, mz))
    mushrooms.append(mp)
    h = random.uniform(0.35, 0.65)
    smooth_cone(f"mush_{mk}_stem", r1=0.08, r2=0.06, depth=h, segs=10, loc=(0, h / 2, 0), parent=mp, mat=MAT_MUSH_STEM)
    cap = MAT_MUSH_CAP if mk % 2 == 0 else MAT_MUSH_CAP2
    smooth_sphere(f"mush_{mk}_cap", r=0.22, segs=18, rings=12, loc=(0, h + 0.10, 0), parent=mp, mat=cap, scale=(1.0, 0.55, 1.0))
    mp["_phase"] = mk * 0.30


# --- 12 chauves-souris volant -------------------------------------------
bats = []
for bk in range(12):
    a = bk * (math.pi * 2 / 12) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 8)
    y = random.uniform(4, 8.5)
    bp = empty(f"bat_{bk}_p", (math.cos(a) * r, y, math.sin(a) * r))
    # body
    smooth_sphere(f"bat_{bk}_body", r=0.10, segs=10, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BAT, scale=(1.2, 0.8, 0.8))
    # head
    smooth_sphere(f"bat_{bk}_head", r=0.07, segs=10, rings=6, loc=(0.10, 0.02, 0), parent=bp, mat=MAT_BAT)
    # 2 ears
    for ek, ez in [("L", 0.04), ("R", -0.04)]:
        smooth_cone(f"bat_{bk}_ear_{ek}", r1=0.025, r2=0.0, depth=0.06, segs=6, loc=(0.10, 0.08, ez), parent=bp, mat=MAT_BAT)
    # 2 wings
    wL = empty(f"bat_{bk}_wL", (0, 0, 0.05), parent=bp)
    wR = empty(f"bat_{bk}_wR", (0, 0, -0.05), parent=bp)
    smooth_sphere(f"bat_{bk}_wL_b", r=0.18, segs=12, rings=6, loc=(0, 0, 0.20), parent=wL, mat=MAT_BAT_WING, scale=(1.0, 0.05, 1.6))
    smooth_sphere(f"bat_{bk}_wR_b", r=0.18, segs=12, rings=6, loc=(0, 0, -0.20), parent=wR, mat=MAT_BAT_WING, scale=(1.0, 0.05, 1.6))
    bats.append({"p": bp, "wL": wL, "wR": wR, "a": a, "r": r, "y": y, "phase": bk * 0.4})


# --- 50 magic particles drift 3D ----------------------------------------
magic_parts = []
for mk in range(50):
    pmat = MAT_MAGIC_A if mk % 2 == 0 else MAT_MAGIC_B
    px = random.uniform(-7, 7)
    py = random.uniform(2, 8)
    pz = random.uniform(-3, 6)
    mp = smooth_sphere(f"magic_{mk}", r=random.uniform(0.04, 0.07), segs=8, rings=6, loc=(px, py, pz), mat=pmat)
    mp["_base"] = (px, py, pz)
    mp["_phase"] = mk * 0.13
    magic_parts.append(mp)


# --- 5 cristaux pendants suspendus (from vault) -------------------------
pendants = []
for pk in range(5):
    pa = pk * (math.pi * 2 / 5) + 0.4
    pr = 2.5
    px = math.cos(pa) * pr
    pz = math.sin(pa) * pr
    py_top = 8.5
    # chain/string (cone thin)
    smooth_cone(f"pendant_{pk}_chain", r1=0.015, r2=0.015, depth=1.5, segs=4, loc=(px, py_top - 0.75, pz), mat=MAT_STALAC)
    pp = empty(f"pendant_{pk}_p", (px, py_top - 1.5, pz))
    pendants.append(pp)
    cmat = crystal_mats[pk]
    # 6-sided crystal diamond
    smooth_cone(f"pendant_{pk}_top", r1=0.0, r2=0.14, depth=0.25, segs=6, loc=(0, 0.12, 0), parent=pp, mat=cmat)
    pbot = smooth_cone(f"pendant_{pk}_bot", r1=0.0, r2=0.14, depth=0.20, segs=6, loc=(0, -0.10, 0), parent=pp, mat=cmat)
    pbot.rotation_euler = (math.radians(180), 0, 0)
    pp["_phase"] = pk * 0.5
    pp["_base"] = (px, py_top - 1.5, pz)


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

    # 100 geode crystals : wave of pulse propagated from center
    for gc in geode_crystals:
        rd = gc["radial_dist"]
        ph = gc["phase"]
        # wave : pulse triggers based on radial distance
        wave_phase = (tt * 2 * math.pi - rd * 2.5) + ph * 0.5
        pulse = 0.85 + 0.40 * math.sin(wave_phase)
        kf(gc["p"], f, "scale", (pulse, pulse, pulse))

    # 30 stalactites : légère vibration
    for sti, sp_obj in enumerate(stalactites):
        ph = sp_obj["_phase"]
        sway = math.radians(2) * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(sp_obj, f, "rotation_euler", (sway, 0, math.radians(1.5 * math.cos(2 * math.pi * tt * 2.5 + ph * math.pi))))

    # 8 floating crystals : orbit + rotate XYZ
    for fc in floating_crystals:
        ang = fc["a"] + tt * 2 * math.pi * 0.4
        fx_ = math.cos(ang) * fc["r"]
        fz_ = math.sin(ang) * fc["r"]
        fy_ = fc["y0"] + 0.4 * math.sin(2 * math.pi * tt * 1.5 + fc["phase"])
        kf(fc["p"], f, "location", (fx_, fy_, fz_))
        kf(fc["p"], f, "rotation_euler", (math.radians(360 * tt + fc["phase"] * 30), math.radians(540 * tt + fc["phase"] * 60), math.radians(180 * tt + fc["phase"] * 45)))

    # 12 bats : flap + dart erratic
    for bd in bats:
        ang = bd["a"] + tt * 2 * math.pi * 0.5 + 0.3 * math.sin(2 * math.pi * tt * 3 + bd["phase"])
        bx_ = math.cos(ang) * bd["r"] + 0.4 * math.sin(2 * math.pi * tt * 4 + bd["phase"])
        bz_ = math.sin(ang) * bd["r"] + 0.4 * math.cos(2 * math.pi * tt * 4 + bd["phase"])
        by_ = bd["y"] + 0.5 * math.sin(2 * math.pi * tt * 2.5 + bd["phase"])
        kf(bd["p"], f, "location", (bx_, by_, bz_))
        kf(bd["p"], f, "rotation_euler", (math.radians(10 * math.sin(2 * math.pi * tt * 3 + bd["phase"])), ang + math.pi / 2, 0))
        wflap = math.radians(60) * math.sin(2 * math.pi * tt * 12 + bd["phase"])
        kf(bd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(bd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 50 magic particles drift
    for mp in magic_parts:
        bxp, byp, bzp = mp["_base"]
        ph = mp["_phase"]
        nx = bxp + 0.7 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        ny = byp + 0.5 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi)
        nz = bzp + 0.6 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi * 0.7)
        kf(mp, f, "location", (nx, ny, nz))
        sc = 0.6 + 0.6 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(mp, f, "scale", (sc, sc, sc))

    # 5 pendants sway
    for pp in pendants:
        bx_, by_, bz_ = pp["_base"]
        ph = pp["_phase"]
        sway_x = bx_ + 0.15 * math.sin(2 * math.pi * tt * 1.2 + ph * math.pi)
        sway_z = bz_ + 0.10 * math.cos(2 * math.pi * tt * 1.5 + ph * math.pi)
        kf(pp, f, "location", (sway_x, by_, sway_z))
        kf(pp, f, "rotation_euler", (math.radians(8 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)), math.radians(180 * tt + ph * 60), 0))

    # 10 ripples : expansion + fade
    for ri, rp in enumerate(ripples):
        ph = rp["_phase"]
        local = (tt * 2 + ph) % 1.0
        sc = 1.0 + local * 1.5
        kf(rp, f, "scale", (sc, 1.0, sc))

    # 6 mushrooms pulse émission via scale
    for mp_obj in mushrooms:
        ph = mp_obj["_phase"]
        ms = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(mp_obj, f, "scale", (ms, ms, ms))

    # entrance glow pulse
    eg = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 1.5)
    kf(entrance_p, f, "scale", (eg, eg, eg))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_crystal_cave_geode] wrote {OUT}")
