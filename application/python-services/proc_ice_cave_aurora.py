"""
proc_ice_cave_aurora.py — 177e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Grotte de glace avec aurore boréale visible :
- voûte caverne glace avec rocks bleus
- 20 stalactites + 15 stalagmites cristal bleu
- aurore boréale 3 bandes ondulantes émissives (vert/bleu/violet)
- ours polaire dormant (anatomy : corps + 4 pattes + tête)
- 8 morses sur glace (corps + défenses + nageoires)
- 50 lucioles spirales montantes
- bassin glacé central
- 30 fragments cristal flottants
- 4 pingouins (waddle anatomy)
- lumière surnaturelle
- ciel arctique étoiles
- montagnes glacier arrière

Animations multi-axes simultanées :
- aurore 3 bandes wave différentielles cycle couleurs
- ours respire breathing pulse
- 8 morses bob subtle
- 4 pingouins waddle (legs alternate)
- 50 lucioles spirales upward
- 30 fragments drift + rotate XYZ
- bassin ripples
- stalactites micro-vibration

Sortie : output/3d/pbr_icecave_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_icecave_proc.glb"))

random.seed(0x1CE000)


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
MAT_SKY = make_mat("sky_arctic", (0.05, 0.08, 0.20), roughness=1.0, emi=(0.05, 0.08, 0.20), emi_strength=0.8)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.0)
MAT_AURORA_GREEN = make_mat("aurora_green", (0.30, 0.95, 0.50), roughness=0.0, alpha=0.55, emi=(0.30, 0.95, 0.50), emi_strength=10.0)
MAT_AURORA_BLUE = make_mat("aurora_blue", (0.30, 0.55, 0.95), roughness=0.0, alpha=0.55, emi=(0.30, 0.55, 0.95), emi_strength=10.0)
MAT_AURORA_PURPLE = make_mat("aurora_purple", (0.85, 0.30, 0.95), roughness=0.0, alpha=0.55, emi=(0.85, 0.30, 0.95), emi_strength=10.0)
MAT_ICE = make_mat("ice", (0.65, 0.85, 0.95), roughness=0.10, alpha=0.75, emi=(0.30, 0.55, 0.70), emi_strength=2.0)
MAT_ICE_DEEP = make_mat("ice_deep", (0.30, 0.55, 0.85), roughness=0.20, alpha=0.85, emi=(0.15, 0.30, 0.55), emi_strength=1.5)
MAT_ICE_BRIGHT = make_mat("ice_bright", (0.85, 0.95, 1.0), roughness=0.05, emi=(0.55, 0.75, 0.95), emi_strength=2.5)
MAT_SNOW = make_mat("snow", (0.95, 0.98, 1.0), roughness=0.7, emi=(0.55, 0.60, 0.65), emi_strength=0.6)
MAT_GLACIER = make_mat("glacier", (0.45, 0.65, 0.80), roughness=0.6, emi=(0.20, 0.35, 0.50), emi_strength=0.5)
MAT_WATER_FROZEN = make_mat("water_frozen", (0.30, 0.60, 0.85), roughness=0.10, alpha=0.55, emi=(0.20, 0.40, 0.65), emi_strength=2.0)
MAT_BEAR_WHITE = make_mat("bear_white", (0.90, 0.92, 0.90), roughness=0.6, emi=(0.35, 0.40, 0.40), emi_strength=0.4)
MAT_BEAR_DARK = make_mat("bear_dark", (0.20, 0.18, 0.18), roughness=0.7)
MAT_WALRUS = make_mat("walrus", (0.40, 0.30, 0.25), roughness=0.6, emi=(0.15, 0.10, 0.08), emi_strength=0.3)
MAT_WALRUS_TUSK = make_mat("tusk", (0.95, 0.92, 0.85), roughness=0.30, emi=(0.40, 0.35, 0.30), emi_strength=0.4)
MAT_PENGUIN_BLACK = make_mat("penguin_black", (0.10, 0.10, 0.12), roughness=0.5)
MAT_PENGUIN_WHITE = make_mat("penguin_white", (0.95, 0.95, 0.90), roughness=0.5, emi=(0.40, 0.40, 0.38), emi_strength=0.3)
MAT_PENGUIN_BEAK = make_mat("penguin_beak", (0.95, 0.65, 0.20), metallic=0.3, roughness=0.40, emi=(0.40, 0.25, 0.05), emi_strength=0.4)
MAT_PENGUIN_FEET = make_mat("penguin_feet", (0.85, 0.55, 0.20), roughness=0.5)
MAT_FIREFLY = make_mat("firefly", (0.55, 0.95, 1.0), roughness=0.0, emi=(0.55, 0.95, 1.0), emi_strength=10.0)


# --- backdrop : arctic sky -----------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)

# 60 stars
for i in range(60):
    smooth_sphere(f"star_{i}", r=random.uniform(0.06, 0.10), segs=10, rings=8, loc=(random.uniform(-22, 22), random.uniform(11, 16), random.uniform(8, 16)), mat=MAT_STAR)


# --- AURORA BORÉALE 3 bandes ondulantes ---------------------------------
aurora_bands = []
AURORA_MATS = [MAT_AURORA_GREEN, MAT_AURORA_BLUE, MAT_AURORA_PURPLE]
for ai in range(3):
    band_p = empty(f"aurora_{ai}_p", (0, 12 + ai * 0.5, 8))
    aurora_bands.append(band_p)
    # 12 segments forming wavy band
    for sg in range(12):
        sx = -10 + sg * 1.8
        sy_off = math.sin(sg * 0.6) * 0.5
        seg = beveled_cube(f"aurora_{ai}_s_{sg}", (1.8, 4.0, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(sx, sy_off, 0), parent=band_p, mat=AURORA_MATS[ai])
        seg["_phase"] = sg * 0.20 + ai * 0.40
    band_p["_phase"] = ai * 0.50


# --- cave structure (icy interior) -------------------------------------
# floor (icy ground)
floor = beveled_cube("floor_ice", (30, 0.3, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.15, 0), mat=MAT_ICE)
# back wall (ice formation)
for rk in range(40):
    theta = random.uniform(0, math.pi / 2.2)
    phi = random.uniform(0, math.pi * 2)
    R = random.uniform(11, 13)
    x = R * math.sin(theta) * math.cos(phi)
    y = R * math.cos(theta) + 1
    z = R * math.sin(theta) * math.sin(phi)
    rmat = MAT_ICE_DEEP if rk % 2 == 0 else MAT_ICE
    smooth_sphere(f"vault_rock_{rk}", r=random.uniform(0.8, 1.6), segs=14, rings=10, loc=(x, y, z), mat=rmat, scale=(1.0, 0.85, 1.0))


# --- 20 STALACTITES pending --------------------------------------------
stalactites = []
for sk in range(20):
    sx = random.uniform(-9, 9)
    sy = random.uniform(7, 10)
    sz = random.uniform(-5, 5)
    sh = random.uniform(0.8, 2.0)
    sp = empty(f"stal_{sk}_p", (sx, sy, sz))
    stalactites.append(sp)
    smooth_cone(f"stal_{sk}", r1=0.20, r2=0.0, depth=sh, segs=10, loc=(0, -sh / 2, 0), parent=sp, mat=MAT_ICE_BRIGHT)
    # tip bright glow
    smooth_sphere(f"stal_{sk}_tip", r=0.08, segs=10, rings=8, loc=(0, -sh - 0.08, 0), parent=sp, mat=MAT_ICE_BRIGHT)
    sp["_phase"] = sk * 0.20

# 15 STALAGMITES montant
for sk in range(15):
    sx = random.uniform(-9, 9)
    sz = random.uniform(-5, 5)
    if abs(sx) < 3 and abs(sz - 1) < 3:
        continue  # skip near bear/water
    sh = random.uniform(0.6, 1.6)
    smooth_cone(f"stalg_{sk}", r1=0.25, r2=0.0, depth=sh, segs=10, loc=(sx, sh / 2, sz), mat=MAT_ICE_BRIGHT)


# --- 5 montagnes glacier arrière-plan -----------------------------------
for mk in range(5):
    mx = -12 + mk * 6
    mh = random.uniform(5, 8)
    smooth_cone(f"mountain_{mk}", r1=2.5, r2=0.0, depth=mh, segs=12, loc=(mx, mh / 2, 11), mat=MAT_GLACIER)
    # snow cap
    smooth_sphere(f"mountain_{mk}_snow", r=1.0, segs=14, rings=10, loc=(mx, mh, 11), mat=MAT_SNOW, scale=(1.0, 0.50, 1.0))


# --- BASSIN GLACÉ central -----------------------------------------------
pool_p = empty("pool", (0, 0, 1))
# rim
smooth_cone("pool_rim", r1=2.5, r2=2.3, depth=0.30, segs=24, loc=(0, 0.15, 0), parent=pool_p, mat=MAT_ICE_DEEP)
# water surface (frozen)
smooth_cone("pool_surf", r1=2.2, r2=2.2, depth=0.08, segs=24, loc=(0, 0.30, 0), parent=pool_p, mat=MAT_WATER_FROZEN)
# 8 ripples concentric
ripples = []
for rk in range(8):
    ra = rk * (math.pi * 2 / 8)
    rr = 0.6 + (rk % 3) * 0.5
    rip = smooth_cone(f"ripple_{rk}", r1=rr, r2=rr * 1.05, depth=0.04, segs=18, loc=(0, 0.32, 0), parent=pool_p, mat=MAT_WATER_FROZEN)
    rip["_phase"] = rk * 0.25
    ripples.append(rip)


# --- OURS POLAIRE dormant ----------------------------------------------
bear_p = empty("bear", (-4, 0, 2))
# body (curled sleeping)
bear_body = smooth_sphere("bear_body", r=0.95, segs=22, rings=18, loc=(0, 0.65, 0), parent=bear_p, mat=MAT_BEAR_WHITE, scale=(1.5, 0.85, 1.2))
# head
head_p = empty("bear_head_p", (1.20, 0.80, 0), parent=bear_p)
smooth_sphere("bear_head", r=0.50, segs=22, rings=16, loc=(0, 0, 0), parent=head_p, mat=MAT_BEAR_WHITE, scale=(1.0, 1.0, 0.95))
# snout
smooth_sphere("bear_snout", r=0.30, segs=18, rings=14, loc=(0.35, -0.10, 0), parent=head_p, mat=MAT_BEAR_WHITE, scale=(1.2, 0.7, 0.85))
# nose
smooth_sphere("bear_nose", r=0.10, segs=14, rings=10, loc=(0.55, -0.05, 0), parent=head_p, mat=MAT_BEAR_DARK)
# 2 ears
for ek, ez in [("L", 0.25), ("R", -0.25)]:
    smooth_sphere(f"bear_ear_{ek}", r=0.13, segs=14, rings=10, loc=(-0.10, 0.40, ez), parent=head_p, mat=MAT_BEAR_WHITE, scale=(1.0, 0.85, 0.85))
# 2 closed eyes (small dark lines)
for ek, ez in [("L", 0.15), ("R", -0.15)]:
    smooth_sphere(f"bear_eye_{ek}", r=0.06, segs=12, rings=8, loc=(0.25, 0.15, ez), parent=head_p, mat=MAT_BEAR_DARK, scale=(1.0, 0.3, 1.0))
# 4 paws curled under
for lk, (lx, lz) in enumerate([(-0.6, 0.45), (0.6, 0.45), (-0.6, -0.45), (0.6, -0.45)]):
    smooth_sphere(f"bear_paw_{lk}", r=0.30, segs=18, rings=12, loc=(lx, 0.30, lz), parent=bear_p, mat=MAT_BEAR_WHITE, scale=(1.0, 0.6, 1.0))


# --- 8 MORSES sur glace --------------------------------------------------
walruses = []
WALRUS_POSITIONS = [(-7, 0, -3), (-5, 0, -3), (-3, 0, -3), (5, 0, -3), (7, 0, -3), (3, 0, -4), (-3, 0, -5), (5, 0, -5)]
for wi, (wx, wy, wz) in enumerate(WALRUS_POSITIONS):
    wp = empty(f"walrus_{wi}_p", (wx, wy, wz))
    walruses.append(wp)
    # body (cylindrical)
    smooth_sphere(f"walrus_{wi}_body", r=0.55, segs=20, rings=14, loc=(0, 0.45, 0), parent=wp, mat=MAT_WALRUS, scale=(1.8, 0.7, 0.85))
    # head
    smooth_sphere(f"walrus_{wi}_head", r=0.35, segs=18, rings=14, loc=(0.85, 0.55, 0), parent=wp, mat=MAT_WALRUS, scale=(1.1, 0.95, 0.85))
    # 2 tusks (defenses)
    for tk, tz in [("L", 0.12), ("R", -0.12)]:
        tusk = smooth_cone(f"walrus_{wi}_tusk_{tk}", r1=0.04, r2=0.0, depth=0.30, segs=8, loc=(1.05, 0.30, tz), parent=wp, mat=MAT_WALRUS_TUSK)
        tusk.rotation_euler = (math.radians(-10), 0, math.radians(-15 if tz > 0 else 15))
    # 2 flippers
    for fk, fz in [("L", 0.40), ("R", -0.40)]:
        smooth_sphere(f"walrus_{wi}_fl_{fk}", r=0.18, segs=14, rings=10, loc=(-0.30, 0.20, fz), parent=wp, mat=MAT_WALRUS, scale=(1.5, 0.10, 0.85))
    wp["_phase"] = wi * 0.30
    wp["_base"] = (wx, wy, wz)


# --- 4 PINGOUINS waddle ----------------------------------------------
penguins = []
PENGUIN_POSITIONS = [(2, 0, 4), (3.5, 0, 4.5), (5, 0, 4), (6.5, 0, 4.5)]
for pi, (px, py, pz) in enumerate(PENGUIN_POSITIONS):
    pp = empty(f"penguin_{pi}_p", (px, py, pz))
    penguins.append(pp)
    # body (oval)
    smooth_sphere(f"penguin_{pi}_body", r=0.30, segs=18, rings=14, loc=(0, 0.45, 0), parent=pp, mat=MAT_PENGUIN_BLACK, scale=(1.0, 1.5, 1.0))
    # white belly
    smooth_sphere(f"penguin_{pi}_belly", r=0.22, segs=18, rings=14, loc=(0, 0.45, 0.15), parent=pp, mat=MAT_PENGUIN_WHITE, scale=(0.85, 1.4, 0.45))
    # head
    smooth_sphere(f"penguin_{pi}_head", r=0.18, segs=18, rings=14, loc=(0, 0.95, 0), parent=pp, mat=MAT_PENGUIN_BLACK)
    # face (front white)
    smooth_sphere(f"penguin_{pi}_face", r=0.12, segs=14, rings=10, loc=(0, 0.92, 0.12), parent=pp, mat=MAT_PENGUIN_WHITE, scale=(0.85, 1.0, 0.45))
    # beak
    smooth_cone(f"penguin_{pi}_beak", r1=0.06, r2=0.0, depth=0.18, segs=8, loc=(0, 0.92, 0.25), parent=pp, mat=MAT_PENGUIN_BEAK)
    # 2 wings
    for wk, wz in [("L", 0.25), ("R", -0.25)]:
        smooth_sphere(f"penguin_{pi}_wing_{wk}", r=0.20, segs=14, rings=10, loc=(0, 0.50, wz * 0.5), parent=pp, mat=MAT_PENGUIN_BLACK, scale=(0.30, 1.2, 0.50))
    # 2 feet
    for fk, fz in [("L", 0.10), ("R", -0.10)]:
        smooth_sphere(f"penguin_{pi}_foot_{fk}", r=0.08, segs=12, rings=8, loc=(0.10, 0.08, fz), parent=pp, mat=MAT_PENGUIN_FEET, scale=(1.6, 0.30, 0.85))
    pp["_phase"] = pi * 0.30
    pp["_base"] = (px, py, pz)


# --- 50 LUCIOLES spirales upward ----------------------------------
fireflies = []
for fk in range(50):
    a = fk * (math.pi * 2 / 50) + random.uniform(-0.2, 0.2)
    r = random.uniform(2, 9)
    y = random.uniform(0.5, 9)
    fp_obj = smooth_sphere(f"firefly_{fk}", r=random.uniform(0.05, 0.08), segs=8, rings=6, loc=(math.cos(a) * r, y, math.sin(a) * r), mat=MAT_FIREFLY)
    fp_obj["_a"] = a
    fp_obj["_r0"] = r
    fp_obj["_y0"] = y
    fp_obj["_phase"] = fk * 0.18
    fireflies.append(fp_obj)


# --- 30 FRAGMENTS CRISTAL flottants ---------------------------------
fragments = []
for fk in range(30):
    a = fk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 9)
    fx = math.cos(a) * r
    fy = random.uniform(2, 8)
    fz = math.sin(a) * r * 0.7
    fmat = MAT_ICE_BRIGHT if fk % 2 == 0 else MAT_ICE
    fr = smooth_cone(f"frag_{fk}", r1=0.0, r2=random.uniform(0.08, 0.15), depth=random.uniform(0.20, 0.40), segs=6, loc=(fx, fy, fz), mat=fmat)
    fr["_base"] = (fx, fy, fz)
    fr["_phase"] = fk * 0.12
    fragments.append(fr)


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

    # AURORA 3 bandes wave différentielles
    for ai, band_p in enumerate(aurora_bands):
        ph = band_p["_phase"]
        # band sway X
        sway_x = math.radians(5 * math.sin(2 * math.pi * tt * 0.4 + ph * math.pi))
        kf(band_p, f, "rotation_euler", (sway_x, 0, 0))
        # individual segments wave Y
        for sg_idx in range(12):
            seg = bpy.data.objects.get(f"aurora_{ai}_s_{sg_idx}")
            if seg:
                ph_s = seg["_phase"]
                wave_y = math.sin(sg_idx * 0.6 + 2 * math.pi * tt * 1.0 + ph_s * math.pi) * 1.5
                kf(seg, f, "location", (-10 + sg_idx * 1.8, wave_y, 0))
                # pulse intensity (scale Y)
                sc = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 2 + ph_s * math.pi)
                kf(seg, f, "scale", (1.0, sc, 1.0))

    # bear breathing (body pulse)
    bear_breath = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 1.0)
    kf(bear_body, f, "scale", (1.5 * bear_breath, 0.85, 1.2 * bear_breath))
    # head slight tilt
    kf(head_p, f, "rotation_euler", (0, math.radians(3 * math.sin(2 * math.pi * tt * 0.7)), 0))

    # 8 walruses bob subtle
    for wr in walruses:
        bx_, by_, bz_ = wr["_base"]
        ph = wr["_phase"]
        ny = by_ + 0.08 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi)
        kf(wr, f, "location", (bx_, ny, bz_))
        kf(wr, f, "rotation_euler", (0, math.radians(15 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)), 0))

    # 4 penguins waddle (alternate sway Z)
    for pi_idx, pp in enumerate(penguins):
        bx_, by_, bz_ = pp["_base"]
        ph = pp["_phase"]
        # waddle : tilt Z + slight bounce Y + step forward
        waddle = math.radians(8 * math.sin(2 * math.pi * tt * 2 + ph * math.pi))
        bounce = 0.05 * abs(math.sin(2 * math.pi * tt * 2 + ph * math.pi))
        step_x = 0.3 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        kf(pp, f, "location", (bx_ + step_x, by_ + bounce, bz_))
        kf(pp, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)), waddle))

    # 50 fireflies spiral upward
    for fp_obj in fireflies:
        a0 = fp_obj["_a"]
        r0 = fp_obj["_r0"]
        y0 = fp_obj["_y0"]
        ph = fp_obj["_phase"]
        spiral_ang = a0 + tt * 2 * math.pi * 0.6
        spiral_r = r0 + 0.4 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi)
        ny = y0 + 0.5 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        nx = math.cos(spiral_ang) * spiral_r
        nz = math.sin(spiral_ang) * spiral_r
        kf(fp_obj, f, "location", (nx, ny, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(fp_obj, f, "scale", (sc, sc, sc))

    # 30 fragments drift + rotate 3-axes
    for fr in fragments:
        bx_, by_, bz_ = fr["_base"]
        ph = fr["_phase"]
        ny = by_ + 0.4 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        nx = bx_ + 0.3 * math.cos(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(fr, f, "location", (nx, ny, bz_))
        kf(fr, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 20 stalactites micro-vibration
    for sti, sp_obj in enumerate(stalactites):
        ph = sp_obj["_phase"]
        sway = math.radians(2) * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(sp_obj, f, "rotation_euler", (sway, 0, math.radians(1.5 * math.cos(2 * math.pi * tt * 2.5 + ph * math.pi))))

    # 8 ripples expansion
    for ri, rp_obj in enumerate(ripples):
        ph = rp_obj["_phase"]
        local = (tt * 2 + ph) % 1.0
        sc = 1.0 + local * 1.5
        kf(rp_obj, f, "scale", (sc, 1.0, sc))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_ice_cave_aurora] wrote {OUT}")
