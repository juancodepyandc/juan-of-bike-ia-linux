"""
proc_dragon_egg_lava.py — 170e procédural AuroraIA, MILESTONE 170e + 34e qualité.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie articulée).

Œuf dragon éclatant dans lave volcanique :
- œuf dragon géant craquelé bevelé révélant lave intérieure émissive
- bébé dragon émergeant (tête + 1 patte griffue + 1 aile dépliée)
- rivières de lave qui coulent
- 8 bulles lave bouillonnante
- cratère volcanique fond
- 30 roches obsidiennes
- 4 émissions feu jaillissantes
- nuages cendres flottantes
- 50 étincelles parabolic
- ciel apocalyptique rouge + soleil mourant
- 12 fragments roche flottants
- 6 cracks émissifs sur l'œuf (lava lignes interior)

Animations multi-axes simultanées :
- œuf vibrer subtil + scale pulse cracks
- bébé dragon émerge progressivement (head lift + eye open + wing unfold + claw paw out)
- lave rivières flow Y
- 8 bulles lave pulse intense
- 4 émissions feu jaillissent cycliques
- 50 étincelles parabolic trajectories
- 12 fragments drift + rotate 3-axes
- cendres drift
- soleil mourant pulse

Sortie : output/3d/pbr_dragonegg_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_dragonegg_proc.glb"))

random.seed(0xD2A607)


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
MAT_SKY = make_mat("sky_apoc", (0.55, 0.10, 0.10), roughness=1.0, emi=(0.55, 0.10, 0.10), emi_strength=1.5)
MAT_SUN_DYING = make_mat("sun_dying", (1.0, 0.35, 0.10), roughness=0.0, emi=(1.0, 0.35, 0.10), emi_strength=14.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.40, 0.10), roughness=0.0, alpha=0.30, emi=(1.0, 0.40, 0.10), emi_strength=4.0)
MAT_CRATER = make_mat("crater", (0.10, 0.06, 0.05), roughness=0.95)
MAT_OBSIDIAN = make_mat("obsidian", (0.10, 0.08, 0.10), metallic=0.4, roughness=0.20, emi=(0.05, 0.04, 0.05), emi_strength=0.3)
MAT_LAVA = make_mat("lava", (1.0, 0.30, 0.05), roughness=0.20, emi=(1.0, 0.30, 0.05), emi_strength=10.0)
MAT_LAVA_BRIGHT = make_mat("lava_bright", (1.0, 0.65, 0.15), roughness=0.10, emi=(1.0, 0.65, 0.15), emi_strength=14.0)
MAT_LAVA_DEEP = make_mat("lava_deep", (0.85, 0.15, 0.05), roughness=0.30, emi=(0.85, 0.15, 0.05), emi_strength=8.0)
MAT_EGG_SHELL = make_mat("egg_shell", (0.50, 0.40, 0.35), roughness=0.65, emi=(0.20, 0.15, 0.12), emi_strength=0.5)
MAT_EGG_CRACK = make_mat("egg_crack", (1.0, 0.55, 0.15), roughness=0.10, emi=(1.0, 0.55, 0.15), emi_strength=12.0)
MAT_EGG_DARK = make_mat("egg_dark", (0.25, 0.20, 0.18), roughness=0.75)
MAT_DRAGON_SCALE = make_mat("dragon_scale", (0.55, 0.10, 0.08), roughness=0.55, emi=(0.25, 0.05, 0.04), emi_strength=0.5)
MAT_DRAGON_SCALE_DARK = make_mat("dragon_scale_dark", (0.30, 0.05, 0.04), roughness=0.65)
MAT_DRAGON_BELLY = make_mat("dragon_belly", (0.95, 0.55, 0.15), roughness=0.5, emi=(0.45, 0.25, 0.05), emi_strength=0.8)
MAT_DRAGON_HORN = make_mat("dragon_horn", (0.85, 0.65, 0.30), metallic=0.4, roughness=0.30, emi=(0.35, 0.25, 0.10), emi_strength=0.4)
MAT_DRAGON_EYE = make_mat("dragon_eye", (1.0, 0.85, 0.20), roughness=0.0, emi=(1.0, 0.85, 0.20), emi_strength=15.0)
MAT_DRAGON_WING = make_mat("dragon_wing", (0.55, 0.15, 0.10), roughness=0.65, alpha=0.85, emi=(0.30, 0.05, 0.05), emi_strength=0.5)
MAT_CLAW = make_mat("claw", (0.20, 0.15, 0.10), metallic=0.5, roughness=0.30)
MAT_SPARK = make_mat("spark", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_ASH = make_mat("ash", (0.30, 0.28, 0.25), roughness=1.0, alpha=0.50, emi=(0.20, 0.18, 0.18), emi_strength=0.6)
MAT_SMOKE = make_mat("smoke", (0.20, 0.15, 0.15), roughness=1.0, alpha=0.55, emi=(0.15, 0.10, 0.10), emi_strength=0.5)
MAT_FLAME = make_mat("flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=15.0)


# --- backdrop : apocalyptic ---------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)

# dying sun
sun_p = empty("sun_p", (-9, 13, 10))
sun = smooth_sphere("sun_dying", r=1.6, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_DYING)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.5, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=3.4, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)


# --- crater (volcanic ground) -----------------------------------------
crater_p = empty("crater_p", (0, 0, 0))
ground = beveled_cube("ground", (35, 0.3, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.15, 0), parent=crater_p, mat=MAT_CRATER)
# crater rim (raised perimeter)
for ck in range(12):
    ca = ck * (math.pi * 2 / 12)
    cx = math.cos(ca) * 8
    cz = math.sin(ca) * 6
    smooth_sphere(f"rim_{ck}", r=random.uniform(0.6, 1.2), segs=14, rings=10, loc=(cx, 0.50, cz), parent=crater_p, mat=MAT_CRATER, scale=(1.0, 0.85, 1.0))

# 30 obsidian rocks
for rk in range(30):
    a = rk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(4, 10)
    rx = math.cos(a) * r
    rz = math.sin(a) * r * 0.7
    smooth_sphere(f"obs_{rk}", r=random.uniform(0.25, 0.60), segs=14, rings=10, loc=(rx, 0.20, rz), mat=MAT_OBSIDIAN, scale=(1.0, 0.80, 1.0))


# --- LAVA RIVERS (visible flowing rivers) -----------------------------
lava_rivers = []
for lk in range(4):
    la = lk * (math.pi * 2 / 4) + 0.5
    # river path with 6 segments
    for sg in range(6):
        srad = 2.0 + sg * 1.0
        lx = math.cos(la) * srad
        lz = math.sin(la) * srad * 0.7
        lava_seg = smooth_sphere(f"lava_river_{lk}_{sg}", r=0.35, segs=14, rings=10, loc=(lx, 0.15, lz), mat=MAT_LAVA, scale=(1.0, 0.30, 1.0))
        lava_seg["_phase"] = sg * 0.20
        lava_seg["_pulse_phase"] = lk * 0.30
        lava_rivers.append(lava_seg)

# central lava pool around egg
pool_p = empty("pool_p", (0, 0, 0))
smooth_sphere("pool_lava", r=2.5, segs=24, rings=14, loc=(0, 0.20, 0), parent=pool_p, mat=MAT_LAVA, scale=(1.0, 0.20, 1.0))
# pool bright center
smooth_sphere("pool_bright", r=1.8, segs=20, rings=12, loc=(0, 0.25, 0), parent=pool_p, mat=MAT_LAVA_BRIGHT, scale=(1.0, 0.15, 1.0))

# 8 lava bubbles in pool
lava_bubs = []
for bk in range(8):
    ba = bk * (math.pi * 2 / 8) + 0.3
    br = 0.8 + (bk % 2) * 0.4
    bx = math.cos(ba) * br
    bz = math.sin(ba) * br
    bub = smooth_sphere(f"lava_bub_{bk}", r=0.20, segs=14, rings=10, loc=(bx, 0.30, bz), mat=MAT_LAVA_BRIGHT)
    bub["_phase"] = bk * 0.18
    lava_bubs.append(bub)


# --- ŒUF DRAGON GÉANT centre ------------------------------------------
egg_p = empty("egg", (0, 0.30, 0))
# main shell (sphere ovoid)
egg_shell = smooth_sphere("egg_shell", r=1.5, segs=32, rings=22, loc=(0, 1.4, 0), parent=egg_p, mat=MAT_EGG_SHELL, scale=(0.85, 1.20, 0.85))
# dark detail patches (8 spots)
for pk in range(8):
    pa = pk * (math.pi * 2 / 8) + random.uniform(-0.2, 0.2)
    pr = 1.55
    px = math.cos(pa) * pr * 0.7
    py = random.uniform(0.5, 2.0)
    pz = math.sin(pa) * pr * 0.7
    smooth_sphere(f"egg_spot_{pk}", r=random.uniform(0.15, 0.25), segs=12, rings=8, loc=(px, py, pz), parent=egg_p, mat=MAT_EGG_DARK, scale=(1.0, 0.3, 1.0))

# 6 cracks (luminescent lines on shell)
for ck in range(6):
    ca = ck * (math.pi * 2 / 6)
    # vertical crack (from top to bottom of egg)
    for sk in range(8):
        t_pos = sk / 7
        cx_pos = math.cos(ca) * 1.20 * math.sin(t_pos * math.pi)
        cy_pos = 0.5 + t_pos * 1.8
        cz_pos = math.sin(ca) * 1.20 * math.sin(t_pos * math.pi)
        crack = smooth_cone(f"crack_{ck}_{sk}", r1=0.03, r2=0.03, depth=0.25, segs=4, loc=(cx_pos, cy_pos, cz_pos), parent=egg_p, mat=MAT_EGG_CRACK)
        crack["_phase"] = (ck * 8 + sk) * 0.05

# top of egg cracked open (broken half)
broken_top_p = empty("broken_top_p", (0, 2.6, 0), parent=egg_p)
# 3 fragments tilted outward
for fk in range(3):
    fa = fk * (math.pi * 2 / 3)
    frag = smooth_sphere(f"egg_frag_{fk}", r=0.40, segs=14, rings=10, loc=(math.cos(fa) * 0.55, 0.25, math.sin(fa) * 0.55), parent=broken_top_p, mat=MAT_EGG_SHELL, scale=(0.7, 0.3, 0.7))
    frag.rotation_euler = (math.radians(30 * math.cos(fa)), 0, math.radians(30 * math.sin(fa)))

# lava interior glow (visible through cracks/top)
smooth_sphere("egg_interior", r=1.0, segs=20, rings=14, loc=(0, 1.6, 0), parent=egg_p, mat=MAT_LAVA, scale=(0.85, 1.0, 0.85))


# --- BÉBÉ DRAGON ÉMERGEANT ---------------------------------------------
baby_p = empty("baby", (0, 2.0, 0))

# head (lifting out of egg)
head_p = empty("baby_head_p", (0, 0.80, 0.20), parent=baby_p)
head = smooth_sphere("baby_head", r=0.30, segs=24, rings=18, loc=(0, 0.20, 0), parent=head_p, mat=MAT_DRAGON_SCALE, scale=(1.0, 1.1, 1.0))
# jaw
smooth_sphere("baby_jaw", r=0.22, segs=18, rings=12, loc=(0, 0.05, 0.15), parent=head_p, mat=MAT_DRAGON_SCALE_DARK, scale=(1.4, 0.5, 0.95))
# snout
smooth_cone("baby_snout", r1=0.20, r2=0.10, depth=0.30, segs=14, loc=(0, 0.20, 0.30), parent=head_p, mat=MAT_DRAGON_SCALE)
# 2 horns
for hk, hz in [("L", 0.10), ("R", -0.10)]:
    horn = smooth_cone(f"baby_horn_{hk}", r1=0.04, r2=0.0, depth=0.30, segs=8, loc=(0, 0.45, hz), parent=head_p, mat=MAT_DRAGON_HORN)
    horn.rotation_euler = (math.radians(-25), 0, math.radians(-15 if hz > 0 else 15))
# 2 eyes (one will open during animation)
eye_L = smooth_sphere("baby_eye_L", r=0.07, segs=14, rings=10, loc=(0.10, 0.30, 0.22), parent=head_p, mat=MAT_DRAGON_EYE)
eye_R = smooth_sphere("baby_eye_R", r=0.07, segs=14, rings=10, loc=(-0.10, 0.30, 0.22), parent=head_p, mat=MAT_DRAGON_EYE)
# nostrils (small dark)
for nk, nz in [("L", 0.06), ("R", -0.06)]:
    smooth_sphere(f"baby_nostril_{nk}", r=0.025, segs=8, rings=6, loc=(0, 0.25, 0.42 + 0.0 * nz), parent=head_p, mat=MAT_EGG_DARK)
# 8 small scale spikes on head
for sk in range(8):
    sa = sk * (math.pi * 2 / 8)
    smooth_cone(f"baby_spike_{sk}", r1=0.03, r2=0.0, depth=0.12, segs=6, loc=(math.cos(sa) * 0.22, 0.40, math.sin(sa) * 0.22), parent=head_p, mat=MAT_DRAGON_HORN)

# Visible paw with claws (emerging from side)
paw_p = empty("baby_paw_p", (0.55, 0.30, 0.10), parent=baby_p)
paw_p.rotation_euler = (0, 0, math.radians(-30))
smooth_sphere("baby_paw_body", r=0.20, segs=18, rings=14, loc=(0, 0, 0), parent=paw_p, mat=MAT_DRAGON_SCALE, scale=(0.8, 1.0, 0.7))
# 4 claws
for ck in range(4):
    ca = ck * (math.pi * 2 / 4) + 0.2
    claw = smooth_cone(f"baby_claw_{ck}", r1=0.025, r2=0.0, depth=0.15, segs=6, loc=(math.cos(ca) * 0.18, -0.05, math.sin(ca) * 0.18), parent=paw_p, mat=MAT_CLAW)

# Visible wing (folded but partially deployed)
wing_p = empty("baby_wing_p", (-0.45, 0.50, 0), parent=baby_p)
wing_p.rotation_euler = (0, math.radians(-30), math.radians(-20))
# wing main bone
smooth_cone("baby_wing_bone", r1=0.06, r2=0.04, depth=0.85, segs=8, loc=(0, 0.40, 0), parent=wing_p, mat=MAT_DRAGON_SCALE_DARK)
# 4 phalanges fanning out
for ph in range(4):
    pa = -0.15 + ph * 0.10
    phal = smooth_cone(f"baby_wing_ph_{ph}", r1=0.03, r2=0.015, depth=0.55, segs=6, loc=(pa, 0.85, 0), parent=wing_p, mat=MAT_DRAGON_SCALE_DARK)
    phal.rotation_euler = (0, 0, math.radians(15 + ph * 10))
# wing membrane (3 panels alpha)
for mk in range(3):
    ma = -0.10 + mk * 0.15
    smooth_sphere(f"baby_wing_mb_{mk}", r=0.30, segs=14, rings=10, loc=(ma, 0.80, 0), parent=wing_p, mat=MAT_DRAGON_WING, scale=(1.2, 0.05, 1.5))


# --- 4 émissions feu jaillissantes -----------------------------------
fire_emit = []
for fk in range(4):
    fa = fk * (math.pi * 2 / 4) + math.pi / 4
    fr = 5
    fx = math.cos(fa) * fr
    fz = math.sin(fa) * fr * 0.7
    fp = empty(f"fire_{fk}_p", (fx, 0.20, fz))
    # main flame
    flame_out = smooth_sphere(f"fire_{fk}_out", r=0.50, segs=18, rings=14, loc=(0, 1.0, 0), parent=fp, mat=MAT_FLAME, scale=(0.8, 1.8, 0.8))
    flame_in = smooth_sphere(f"fire_{fk}_in", r=0.30, segs=14, rings=10, loc=(0, 1.0, 0), parent=fp, mat=MAT_LAVA_BRIGHT, scale=(0.6, 2.0, 0.6))
    fp["_phase"] = fk * 0.40
    fire_emit.append({"p": fp, "out": flame_out, "in": flame_in, "phase": fk * 0.40})


# --- 50 sparks parabolic ----------------------------------------------
sparks = []
for sk in range(50):
    a = sk * (math.pi * 2 / 50) + random.uniform(-0.3, 0.3)
    r = random.uniform(0.5, 4.0)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    sp_obj = smooth_sphere(f"spark_{sk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(sx, 0.5, sz), mat=MAT_SPARK)
    sp_obj["_base_x"] = sx
    sp_obj["_base_z"] = sz
    sp_obj["_phase"] = sk * 0.10
    sp_obj["_speed"] = random.uniform(0.8, 1.6)
    sparks.append(sp_obj)


# --- 12 fragments flottants ------------------------------------------
fragments = []
for fk in range(12):
    a = fk * (math.pi * 2 / 12) + random.uniform(-0.3, 0.3)
    r = random.uniform(3, 8)
    fx = math.cos(a) * r
    fy = random.uniform(2, 6)
    fz = math.sin(a) * r * 0.7
    fr = beveled_cube(f"frag_{fk}", (random.uniform(0.20, 0.40), random.uniform(0.15, 0.25), random.uniform(0.20, 0.35)), bevel_offset=0.02, bevel_segments=2, loc=(fx, fy, fz), mat=MAT_OBSIDIAN)
    fr["_base"] = (fx, fy, fz)
    fr["_phase"] = fk * 0.12
    fragments.append(fr)


# --- 25 cendres ash drift ---------------------------------------------
ashes = []
for ak in range(25):
    ax = random.uniform(-12, 12)
    ay = random.uniform(3, 9)
    az = random.uniform(-4, 6)
    asp = smooth_sphere(f"ash_{ak}", r=random.uniform(0.06, 0.12), segs=8, rings=6, loc=(ax, ay, az), mat=MAT_ASH)
    asp["_base"] = (ax, ay, az)
    asp["_phase"] = ak * 0.20
    ashes.append(asp)


# --- 6 smoke puffs above flames --------------------------------------
smokes = []
for sk in range(6):
    sa = sk * (math.pi * 2 / 6) + 0.4
    sx = math.cos(sa) * 4.5
    sz = math.sin(sa) * 4.5 * 0.7
    smp = smooth_sphere(f"smoke_{sk}", r=0.50, segs=14, rings=10, loc=(sx, 3.0, sz), mat=MAT_SMOKE, scale=(1.2, 1.0, 1.2))
    smp["_phase"] = sk * 0.25
    smp["_base_x"] = sx
    smp["_base_z"] = sz
    smokes.append(smp)


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

    # œuf vibrate (slight rotation + scale)
    egg_vib_x = math.radians(3 * math.sin(2 * math.pi * tt * 5))
    egg_vib_z = math.radians(3 * math.cos(2 * math.pi * tt * 6))
    kf(egg_p, f, "rotation_euler", (egg_vib_x, 0, egg_vib_z))
    es = 1.0 + 0.03 * math.sin(2 * math.pi * tt * 4)
    kf(egg_shell, f, "scale", (0.85 * es, 1.20 * es, 0.85 * es))

    # bébé dragon hatching progressive (over 6 sec, hatching peaks at tt 0.4-1.0)
    hatch_progress = max(0.0, (tt - 0.3) / 0.7)  # 0..1 after tt=0.3
    # head lift
    head_y = 0.80 + hatch_progress * 0.4
    kf(head_p, f, "location", (0, head_y, 0.20))
    # head turn/tilt
    kf(head_p, f, "rotation_euler", (math.radians(-15 + hatch_progress * 20 + 8 * math.sin(2 * math.pi * tt * 3)), math.radians(15 * math.sin(2 * math.pi * tt * 1.5)), 0))
    # eyes pulse intensity (open during animation)
    eye_pulse = 1.0 + 0.3 * math.sin(2 * math.pi * tt * 4) if hatch_progress > 0.1 else 0.3
    kf(eye_L, f, "scale", (eye_pulse, eye_pulse, eye_pulse))
    kf(eye_R, f, "scale", (eye_pulse, eye_pulse, eye_pulse))
    # wing unfold
    wing_unfold = math.radians(-20 + hatch_progress * 60)
    kf(wing_p, f, "rotation_euler", (0, math.radians(-30 + hatch_progress * 20), wing_unfold + math.radians(5 * math.sin(2 * math.pi * tt * 2))))
    # paw emerges (rotation)
    paw_rot = math.radians(-30 + hatch_progress * 40)
    kf(paw_p, f, "rotation_euler", (0, 0, paw_rot + math.radians(5 * math.cos(2 * math.pi * tt * 3))))

    # 3 broken top fragments rotate slightly
    for ck in [0, 1, 2]:
        frag_obj = bpy.data.objects.get(f"egg_frag_{ck}")
        if frag_obj:
            fa = ck * (math.pi * 2 / 3)
            tilt = math.radians(30 * math.cos(fa) + 5 * math.sin(2 * math.pi * tt * 2 + ck))
            kf(frag_obj, f, "rotation_euler", (tilt, 0, math.radians(30 * math.sin(fa) + 5 * math.cos(2 * math.pi * tt * 2 + ck))))

    # 24 lava rivers : flow Y pulse + emission
    for lava_seg in lava_rivers:
        ph = lava_seg.get("_pulse_phase", 0)
        ny = 0.15 + 0.10 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(lava_seg, f, "location", (lava_seg.location.x if f > 1 else lava_seg.location.x, ny, lava_seg.location.z if f > 1 else lava_seg.location.z))
        sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(lava_seg, f, "scale", (sc, 0.30, sc))

    # 8 lava bubbles : pulse intense
    for lb in lava_bubs:
        ph = lb["_phase"]
        pulse = 1.0 + 0.5 * math.sin(2 * math.pi * tt * 5 + ph * math.pi)
        kf(lb, f, "scale", (pulse, pulse * 0.6, pulse))
        ny = 0.30 + 0.15 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(lb, f, "location", (lb.location.x if f > 1 else lb.location.x, ny, lb.location.z if f > 1 else lb.location.z))

    # 4 fire emissions cyclic jaillissements
    for fe in fire_emit:
        ph = fe["phase"]
        # intermittent peak
        intensity = 0.5 + 0.5 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        fout_sc = 0.5 + intensity * 1.5
        fin_sc = 0.4 + intensity * 1.5
        kf(fe["out"], f, "scale", (fout_sc * 0.8, fout_sc * 1.8, fout_sc * 0.8))
        kf(fe["in"], f, "scale", (fin_sc * 0.6, fin_sc * 2.0, fin_sc * 0.6))
        # sway
        kf(fe["p"], f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 3 + ph)), 0, math.radians(5 * math.cos(2 * math.pi * tt * 3.5 + ph))))

    # 50 sparks parabolic
    for sp_obj in sparks:
        bx_ = sp_obj["_base_x"]
        bz_ = sp_obj["_base_z"]
        ph = sp_obj["_phase"]
        spd = sp_obj["_speed"]
        local = (tt * spd + ph) % 1.0
        py = 0.3 + 4.0 * local * (1 - local)
        nx = bx_ * (1 + local * 0.4)
        nz = bz_ * (1 + local * 0.4)
        kf(sp_obj, f, "location", (nx, py, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 5 + ph * math.pi))
        kf(sp_obj, f, "scale", (sc, sc, sc))

    # 12 fragments drift + rotate 3-axes
    for fr in fragments:
        bx_, by_, bz_ = fr["_base"]
        ph = fr["_phase"]
        ny = by_ + 0.5 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        nx = bx_ + 0.3 * math.cos(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(fr, f, "location", (nx, ny, bz_))
        kf(fr, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 25 ashes drift
    for ap in ashes:
        bx_, by_, bz_ = ap["_base"]
        ph = ap["_phase"]
        nx = bx_ + 0.6 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        ny = by_ + 0.5 * math.cos(2 * math.pi * tt * 0.6 + ph * math.pi)
        nz = bz_ + 0.5 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(ap, f, "location", (nx, ny, nz))

    # 6 smoke puffs above flames
    for sm in smokes:
        ph = sm["_phase"]
        bx_ = sm["_base_x"]
        bz_ = sm["_base_z"]
        local = (tt * 1.2 + ph) % 1.0
        ny = 3.0 + local * 2.5
        sc = 1.0 + local * 1.0
        kf(sm, f, "location", (bx_, ny, bz_))
        kf(sm, f, "scale", (sc, sc, sc))

    # sun mourant pulse
    sp = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 1.5)
    kf(sun, f, "scale", (sp, sp, sp))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_dragon_egg_lava] wrote {OUT}")
