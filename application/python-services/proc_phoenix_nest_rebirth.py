"""
proc_phoenix_nest_rebirth.py — 174e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie articulée).

Nid de phoenix en train de renaître des flammes :
- nid énorme bois bevelé sur arbre mort
- phoenix renaissant : corps articulé + 2 ailes spread + queue plumes longues + tête couronnée + bec doré + 2 yeux émissifs
- flammes intenses 360° entourant
- 30 plumes flammes flottantes émissives
- 4 lava streams
- sun mourant + halos
- arbres secs arrière-plan
- 50 étincelles parabolic
- 12 fragments
- brouillard volcanique
- ciel apocalyptique
- 6 cendres flottantes

Animations multi-axes simultanées :
- phoenix : lift body Y + 2 ailes spread progressively + open tail + eyes open intense + crown halo
- flammes pulse intense 360°
- 30 plumes drift 3D
- lava flow Y
- sun pulse mourant
- 50 étincelles parabolic + scintille
- 6 cendres drift
- 4 arbres morts subtle sway

Sortie : output/3d/pbr_phoenixnest_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_phoenixnest_proc.glb"))

random.seed(0xF1E1AC)


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
MAT_SKY = make_mat("sky_apoc", (0.45, 0.10, 0.05), roughness=1.0, emi=(0.50, 0.15, 0.05), emi_strength=1.8)
MAT_SUN_DYING = make_mat("sun_dying", (1.0, 0.40, 0.10), roughness=0.0, emi=(1.0, 0.40, 0.10), emi_strength=14.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.40, 0.10), roughness=0.0, alpha=0.30, emi=(1.0, 0.40, 0.10), emi_strength=4.0)
MAT_GROUND = make_mat("ground", (0.20, 0.10, 0.06), roughness=0.95, emi=(0.10, 0.05, 0.03), emi_strength=0.4)
MAT_NEST_BRANCH = make_mat("nest_branch", (0.35, 0.20, 0.10), roughness=0.85, emi=(0.18, 0.10, 0.05), emi_strength=0.4)
MAT_NEST_DARK = make_mat("nest_dark", (0.20, 0.12, 0.06), roughness=0.95)
MAT_TREE_DEAD = make_mat("tree_dead", (0.15, 0.10, 0.05), roughness=0.95)
MAT_PHOENIX_BODY = make_mat("phoenix_body", (0.95, 0.30, 0.10), roughness=0.40, emi=(0.85, 0.20, 0.05), emi_strength=2.5)
MAT_PHOENIX_BRIGHT = make_mat("phoenix_bright", (1.0, 0.65, 0.15), roughness=0.20, emi=(1.0, 0.65, 0.15), emi_strength=4.5)
MAT_PHOENIX_BELLY = make_mat("phoenix_belly", (1.0, 0.85, 0.30), roughness=0.30, emi=(1.0, 0.85, 0.30), emi_strength=3.5)
MAT_PHOENIX_WING = make_mat("phoenix_wing", (0.95, 0.40, 0.15), roughness=0.40, alpha=0.95, emi=(0.85, 0.25, 0.08), emi_strength=3.0)
MAT_PHOENIX_TAIL = make_mat("phoenix_tail", (1.0, 0.55, 0.10), roughness=0.30, emi=(1.0, 0.55, 0.10), emi_strength=4.0)
MAT_BEAK_GOLD = make_mat("beak_gold", (1.0, 0.85, 0.30), metallic=0.85, roughness=0.20, emi=(0.55, 0.45, 0.15), emi_strength=1.5)
MAT_PHOENIX_EYE = make_mat("phoenix_eye", (1.0, 1.0, 0.40), roughness=0.0, emi=(1.0, 1.0, 0.40), emi_strength=18.0)
MAT_PHOENIX_CROWN = make_mat("phoenix_crown", (1.0, 0.85, 0.20), metallic=0.90, roughness=0.10, emi=(1.0, 0.85, 0.20), emi_strength=6.0)
MAT_FLAME_OUTER = make_mat("flame_outer", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=16.0)
MAT_FLAME_INNER = make_mat("flame_inner", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.30), emi_strength=22.0)
MAT_FEATHER_FLAME = make_mat("feather_flame", (1.0, 0.55, 0.15), roughness=0.10, alpha=0.85, emi=(1.0, 0.55, 0.15), emi_strength=12.0)
MAT_LAVA = make_mat("lava", (1.0, 0.30, 0.05), roughness=0.20, emi=(1.0, 0.30, 0.05), emi_strength=10.0)
MAT_SPARK = make_mat("spark", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_ASH = make_mat("ash", (0.40, 0.30, 0.25), roughness=1.0, alpha=0.55, emi=(0.30, 0.20, 0.18), emi_strength=0.8)
MAT_FRAGMENT = make_mat("fragment", (0.40, 0.30, 0.22), roughness=0.7)
MAT_FOG = make_mat("fog", (0.30, 0.20, 0.18), roughness=1.0, alpha=0.40, emi=(0.20, 0.12, 0.10), emi_strength=0.6)


# --- backdrop : apocalyptic sky -----------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)

# dying sun
sun_p = empty("sun_p", (-9, 13, 10))
sun = smooth_sphere("sun_dying", r=1.7, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_DYING)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.6, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=3.6, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# ground
ground = beveled_cube("ground", (30, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND)


# --- 5 ARBRES MORTS arrière-plan ----------------------------------
trees_dead = []
TREE_POSITIONS = [(-8, 0, 5), (8, 0, 5), (-10, 0, -2), (10, 0, -2), (0, 0, 7)]
for ti, (tx, ty, tz) in enumerate(TREE_POSITIONS):
    tp = empty(f"tree_{ti}_p", (tx, ty, tz))
    trees_dead.append(tp)
    # twisted trunk
    cur = tp
    for sg in range(3):
        seg_p = empty(f"tree_{ti}_sp_{sg}", (0, 1.0, 0), parent=cur)
        seg_p.rotation_euler = (math.radians(random.uniform(-10, 10)), 0, math.radians(random.uniform(-12, 12)))
        smooth_cone(f"tree_{ti}_s_{sg}", r1=0.25 - sg * 0.04, r2=0.18 - sg * 0.04, depth=1.5, segs=10, loc=(0, 0.75, 0), parent=seg_p, mat=MAT_TREE_DEAD)
        cur = seg_p
    # 6 dead branches
    for bk in range(6):
        ba = bk * (math.pi * 2 / 6) + random.uniform(-0.3, 0.3)
        branch = smooth_cone(f"tree_{ti}_b_{bk}", r1=0.08, r2=0.0, depth=random.uniform(0.8, 1.4), segs=6, loc=(math.cos(ba) * 0.30, random.uniform(0.3, 1.0), math.sin(ba) * 0.30), parent=cur, mat=MAT_TREE_DEAD)
        branch.rotation_euler = (math.radians(60 * math.cos(ba)), 0, math.radians(60 * math.sin(ba)))


# --- NEST GÉANT (huge nest of branches woven) -------------------------
nest_p = empty("nest_p", (0, 2.5, 0))
# main bowl base (using flatten sphere)
nest_base = smooth_sphere("nest_base", r=2.0, segs=24, rings=18, loc=(0, 0, 0), parent=nest_p, mat=MAT_NEST_BRANCH, scale=(1.0, 0.55, 1.0))
# nest "fork" — central tree dead
trunk_p = empty("trunk_p", (0, -2.5, 0), parent=nest_p)
smooth_cone("nest_trunk", r1=0.55, r2=0.40, depth=2.5, segs=14, loc=(0, 1.25, 0), parent=trunk_p, mat=MAT_TREE_DEAD)

# 30 branches forming nest twisted
for bk in range(30):
    ba = bk * (math.pi * 2 / 30)
    bz_off = math.sin(ba) * random.uniform(1.5, 2.0)
    bx_off = math.cos(ba) * random.uniform(1.5, 2.0)
    by_off = random.uniform(0.10, 0.50)
    branch = smooth_cone(f"nest_br_{bk}", r1=0.06, r2=0.04, depth=random.uniform(0.5, 1.0), segs=6, loc=(bx_off, by_off, bz_off), parent=nest_p, mat=MAT_NEST_BRANCH)
    branch.rotation_euler = (math.radians(60 + random.uniform(-15, 15)), random.uniform(0, math.pi * 2), 0)

# 12 darker twigs scattered (inside nest bowl)
for tk in range(12):
    ta = tk * (math.pi * 2 / 12)
    txw = math.cos(ta) * random.uniform(0.5, 1.2)
    tzw = math.sin(ta) * random.uniform(0.5, 1.2)
    smooth_cone(f"nest_twig_{tk}", r1=0.03, r2=0.02, depth=random.uniform(0.3, 0.5), segs=4, loc=(txw, 0.25, tzw), parent=nest_p, mat=MAT_NEST_DARK)


# --- PHOENIX RENAISSANT (center of nest, emerging) -------------------
phoenix_p = empty("phoenix", (0, 3.5, 0))

# body (oval)
body = smooth_sphere("phoenix_body", r=0.55, segs=24, rings=18, loc=(0, 0, 0), parent=phoenix_p, mat=MAT_PHOENIX_BODY, scale=(1.0, 1.4, 1.4))
# belly highlight
smooth_sphere("phoenix_belly", r=0.40, segs=18, rings=14, loc=(0, -0.20, 0.20), parent=phoenix_p, mat=MAT_PHOENIX_BELLY, scale=(1.0, 1.0, 1.5))

# chest plate (bright)
smooth_sphere("phoenix_chest", r=0.30, segs=18, rings=12, loc=(0, 0.10, 0.50), parent=phoenix_p, mat=MAT_PHOENIX_BRIGHT, scale=(1.0, 1.2, 0.85))

# neck
neck_p = empty("neck_p", (0, 0.50, 0.20), parent=phoenix_p)
smooth_cone("phoenix_neck", r1=0.20, r2=0.15, depth=0.40, segs=12, loc=(0, 0.20, 0), parent=neck_p, mat=MAT_PHOENIX_BODY)

# head
head_p = empty("phoenix_head_p", (0, 0.90, 0.30), parent=phoenix_p)
smooth_sphere("phoenix_head", r=0.30, segs=22, rings=16, loc=(0, 0, 0), parent=head_p, mat=MAT_PHOENIX_BODY, scale=(1.0, 1.0, 1.3))
# beak
smooth_cone("phoenix_beak", r1=0.10, r2=0.0, depth=0.30, segs=8, loc=(0, 0.05, 0.35), parent=head_p, mat=MAT_BEAK_GOLD)
# 2 eyes
for ek, ez in [("L", 0.12), ("R", -0.12)]:
    smooth_sphere(f"phoenix_eye_{ek}", r=0.07, segs=14, rings=10, loc=(0, 0.12, 0.25 + ez * 0.2), parent=head_p, mat=MAT_PHOENIX_EYE)

# CROWN (signature phoenix)
crown_p = empty("crown_p", (0, 1.30, 0.30), parent=phoenix_p)
# 7 crown spikes
for ck in range(7):
    ca = -math.pi / 2 + ck * (math.pi / 6.5)
    crown_spike = smooth_cone(f"crown_{ck}", r1=0.04, r2=0.0, depth=0.40 - abs(ca) * 0.15, segs=6, loc=(math.cos(ca) * 0.15, 0, math.sin(ca) * 0.15), parent=crown_p, mat=MAT_PHOENIX_CROWN)
    crown_spike.rotation_euler = (math.radians(-90), 0, ca)

# 2 WINGS spread (large)
wing_L_p = empty("wing_L_p", (0.40, 0.20, 0), parent=phoenix_p)
wing_R_p = empty("wing_R_p", (-0.40, 0.20, 0), parent=phoenix_p)
# wings start folded (will spread during animation)
wing_L_p.rotation_euler = (0, 0, math.radians(-20))
wing_R_p.rotation_euler = (0, 0, math.radians(20))

# wing structure for each side
for side, wing_p, sign in [("L", wing_L_p, 1), ("R", wing_R_p, -1)]:
    # main bone (cone tapered)
    smooth_cone(f"wing_{side}_main", r1=0.08, r2=0.04, depth=2.0, segs=10, loc=(sign * 1.0, 0, 0), parent=wing_p, mat=MAT_PHOENIX_BODY)
    bp = bpy.data.objects.get(f"wing_{side}_main")
    if bp:
        bp.rotation_euler = (0, 0, math.radians(90 * sign))
    # 5 phalanges (fan out)
    for ph in range(5):
        ph_a = -0.4 + ph * 0.20
        phal = smooth_cone(f"wing_{side}_ph_{ph}", r1=0.04, r2=0.02, depth=1.4, segs=6, loc=(sign * 2.0, ph_a * 0.3, 0), parent=wing_p, mat=MAT_PHOENIX_BODY)
        phal.rotation_euler = (0, 0, math.radians(90 * sign + ph_a * 30))
    # 4 membrane patches (fan-shaped feathers)
    for mb in range(4):
        mba = -0.30 + mb * 0.20
        smooth_sphere(f"wing_{side}_mb_{mb}", r=0.40, segs=14, rings=10, loc=(sign * 1.8, mba * 0.4, 0), parent=wing_p, mat=MAT_PHOENIX_WING, scale=(2.0, 0.10, 1.6))

# TAIL (long flame feathers)
tail_p = empty("tail_p", (0, 0, -0.50), parent=phoenix_p)
# 7 long tail feathers fanning out
for tk in range(7):
    ta = -math.pi / 2 + tk * (math.pi / 6.0)
    tail_feather_p = empty(f"tail_f_p_{tk}", (0, 0, 0), parent=tail_p)
    tail_feather_p.rotation_euler = (math.radians(ta * 30), 0, 0)
    # long feather (3 parts: base + mid + tip)
    smooth_cone(f"tail_f_{tk}_b", r1=0.10, r2=0.08, depth=0.50, segs=8, loc=(0, 0, -0.25), parent=tail_feather_p, mat=MAT_PHOENIX_BODY)
    smooth_cone(f"tail_f_{tk}_m", r1=0.08, r2=0.05, depth=0.60, segs=8, loc=(0, 0, -0.85), parent=tail_feather_p, mat=MAT_PHOENIX_TAIL)
    smooth_cone(f"tail_f_{tk}_t", r1=0.05, r2=0.0, depth=0.40, segs=6, loc=(0, 0, -1.35), parent=tail_feather_p, mat=MAT_FLAME_OUTER)

# 2 legs visible
for lk, lx in [("L", 0.15), ("R", -0.15)]:
    # thigh
    smooth_cone(f"leg_{lk}_thigh", r1=0.08, r2=0.06, depth=0.30, segs=8, loc=(lx, -0.30, 0.10), parent=phoenix_p, mat=MAT_PHOENIX_BODY)
    # foot with claws
    smooth_sphere(f"leg_{lk}_foot", r=0.08, segs=10, rings=8, loc=(lx, -0.55, 0.10), parent=phoenix_p, mat=MAT_BEAK_GOLD)
    for ck in range(3):
        ca = ck * (math.pi * 2 / 3)
        claw = smooth_cone(f"leg_{lk}_claw_{ck}", r1=0.02, r2=0.0, depth=0.10, segs=6, loc=(lx + math.cos(ca) * 0.07, -0.62, 0.10 + math.sin(ca) * 0.07), parent=phoenix_p, mat=MAT_BEAK_GOLD)


# --- FLAMMES 360° entourant phoenix (16 flammes radiales) -----------
flames = []
for fk in range(16):
    fa = fk * (math.pi * 2 / 16)
    fr = 1.0 + random.uniform(0, 0.4)
    fx = math.cos(fa) * fr
    fz = math.sin(fa) * fr
    fy = random.uniform(2.5, 3.8)
    fp = empty(f"flame_{fk}_p", (fx, fy, fz))
    # outer flame
    flame_out = smooth_sphere(f"flame_{fk}_out", r=0.30, segs=14, rings=10, loc=(0, 0, 0), parent=fp, mat=MAT_FLAME_OUTER, scale=(0.7, 1.8, 0.7))
    # inner
    flame_in = smooth_sphere(f"flame_{fk}_in", r=0.18, segs=12, rings=8, loc=(0, 0, 0), parent=fp, mat=MAT_FLAME_INNER, scale=(0.5, 2.0, 0.5))
    fp["_phase"] = fk * 0.25
    fp["_base"] = (fx, fy, fz)
    flames.append({"p": fp, "out": flame_out, "in": flame_in, "phase": fk * 0.25})


# --- 30 PLUMES FLAMMES drift 3D -------------------------------------
flame_feathers = []
for fk in range(30):
    a = fk * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(2, 7)
    fy = random.uniform(2, 8)
    fx = math.cos(a) * r
    fz = math.sin(a) * r
    fp = empty(f"flame_f_{fk}_p", (fx, fy, fz))
    # 3 segments tapered feather
    smooth_cone(f"flame_f_{fk}_b", r1=0.06, r2=0.04, depth=0.20, segs=6, loc=(0, 0.05, 0), parent=fp, mat=MAT_PHOENIX_BODY)
    smooth_cone(f"flame_f_{fk}_m", r1=0.04, r2=0.03, depth=0.20, segs=6, loc=(0, 0.20, 0), parent=fp, mat=MAT_PHOENIX_TAIL)
    smooth_cone(f"flame_f_{fk}_t", r1=0.03, r2=0.0, depth=0.20, segs=6, loc=(0, 0.40, 0), parent=fp, mat=MAT_FEATHER_FLAME)
    fp["_base"] = (fx, fy, fz)
    fp["_phase"] = fk * 0.18
    fp["_drift_x"] = random.uniform(0.5, 1.3) * (1 if fk % 2 == 0 else -1)
    flame_feathers.append(fp)


# --- 4 LAVA STREAMS au sol --------------------------------------------
lava_streams = []
for lk in range(4):
    la = lk * (math.pi * 2 / 4) + math.pi / 4
    # 5 segments
    for sg in range(5):
        srad = 2.5 + sg * 1.2
        lx = math.cos(la) * srad
        lz = math.sin(la) * srad
        lava_seg = smooth_sphere(f"lava_str_{lk}_{sg}", r=0.35, segs=14, rings=10, loc=(lx, 0.15, lz), mat=MAT_LAVA, scale=(1.0, 0.30, 1.0))
        lava_seg["_phase"] = sg * 0.20
        lava_seg["_pulse_phase"] = lk * 0.30
        lava_streams.append(lava_seg)


# --- 50 SPARKS parabolic ----------------------------------------------
sparks = []
for sk in range(50):
    a = sk * (math.pi * 2 / 50) + random.uniform(-0.3, 0.3)
    r = random.uniform(1, 5)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    sp_obj = smooth_sphere(f"spark_{sk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(sx, 0.5, sz), mat=MAT_SPARK)
    sp_obj["_base_x"] = sx
    sp_obj["_base_z"] = sz
    sp_obj["_phase"] = sk * 0.10
    sp_obj["_speed"] = random.uniform(0.8, 1.6)
    sparks.append(sp_obj)


# --- 12 FRAGMENTS drift ----------------------------------------------
fragments = []
for fk in range(12):
    a = fk * (math.pi * 2 / 12) + random.uniform(-0.3, 0.3)
    r = random.uniform(3, 8)
    fx = math.cos(a) * r
    fy = random.uniform(2, 6)
    fz = math.sin(a) * r
    fr = beveled_cube(f"frag_{fk}", (random.uniform(0.15, 0.25), random.uniform(0.10, 0.15), random.uniform(0.15, 0.25)), bevel_offset=0.02, bevel_segments=2, loc=(fx, fy, fz), mat=MAT_FRAGMENT)
    fr["_base"] = (fx, fy, fz)
    fr["_phase"] = fk * 0.12
    fragments.append(fr)


# --- 6 ASHES drift ---------------------------------------------------
ashes = []
for ak in range(6):
    ax = random.uniform(-9, 9)
    ay = random.uniform(4, 9)
    az = random.uniform(-4, 6)
    asp = smooth_sphere(f"ash_{ak}", r=random.uniform(0.30, 0.60), segs=14, rings=8, loc=(ax, ay, az), mat=MAT_ASH, scale=(1.0, 0.40, 1.0))
    asp["_base"] = (ax, ay, az)
    asp["_phase"] = ak * 0.25
    ashes.append(asp)


# --- 8 FOG PUFFS brouillard volcanique -----------------------------
fog_puffs = []
for fk in range(8):
    fx = random.uniform(-10, 10)
    fz = random.uniform(-4, 6)
    fy = random.uniform(0.5, 3)
    fp = smooth_sphere(f"fog_{fk}", r=random.uniform(0.8, 1.4), segs=14, rings=8, loc=(fx, fy, fz), mat=MAT_FOG, scale=(1.0, 0.25, 1.0))
    fp["_base"] = (fx, fy, fz)
    fp["_phase"] = fk * 0.30
    fog_puffs.append(fp)


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

    # phoenix rebirth progressive (over 6 sec)
    # rebirth_progress: 0 at tt=0, 1 at tt=1
    rebirth = tt
    # body lift Y
    body_y = 3.5 + rebirth * 0.8 + 0.10 * math.sin(2 * math.pi * tt * 1.5)
    kf(phoenix_p, f, "location", (0, body_y, 0))
    # body roll
    kf(phoenix_p, f, "rotation_euler", (math.radians(3 * math.sin(2 * math.pi * tt * 2)), math.radians(5 * math.sin(2 * math.pi * tt * 0.5)), math.radians(2 * math.cos(2 * math.pi * tt * 2.5))))

    # head tilt + look up
    head_tilt = math.radians(-5 + rebirth * 25 + 5 * math.sin(2 * math.pi * tt * 2))
    kf(head_p, f, "rotation_euler", (head_tilt, math.radians(10 * math.sin(2 * math.pi * tt * 1.2)), 0))

    # WINGS SPREAD (progressively)
    wing_spread = math.radians(-20 + rebirth * 90)
    kf(wing_L_p, f, "rotation_euler", (math.radians(-15 + rebirth * 30), 0, wing_spread))
    kf(wing_R_p, f, "rotation_euler", (math.radians(-15 + rebirth * 30), 0, -wing_spread))

    # tail spread + sway
    kf(tail_p, f, "rotation_euler", (math.radians(rebirth * 30 + 8 * math.sin(2 * math.pi * tt * 1.5)), 0, math.radians(10 * math.cos(2 * math.pi * tt * 1.8))))

    # crown rotate
    kf(crown_p, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 1.5)), 0))

    # 16 flames pulse intense
    for fl in flames:
        ph = fl["phase"]
        intensity = 0.7 + 0.5 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(fl["out"], f, "scale", (intensity * 0.7, intensity * 1.8, intensity * 0.7))
        kf(fl["in"], f, "scale", (intensity * 0.5, intensity * 2.0, intensity * 0.5))
        # flicker rotation
        kf(fl["p"], f, "rotation_euler", (math.radians(8 * math.sin(2 * math.pi * tt * 5 + ph)), 0, math.radians(8 * math.cos(2 * math.pi * tt * 6 + ph))))
        # Y rise subtle
        bx_, by_, bz_ = fl["p"]["_base"]
        ny = by_ + 0.20 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(fl["p"], f, "location", (bx_, ny, bz_))

    # 30 flame feathers drift 3D + rotate
    for ff in flame_feathers:
        bx_, by_, bz_ = ff["_base"]
        ph = ff["_phase"]
        spd = ff["_drift_x"]
        nx = bx_ + 1.0 * math.sin(2 * math.pi * tt * 0.6 * spd + ph * math.pi)
        ny = by_ + 0.8 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi)
        nz = bz_ + 0.7 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(ff, f, "location", (nx, ny, nz))
        kf(ff, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 20 lava stream segments : flow + scale pulse
    for lava_seg in lava_streams:
        ph = lava_seg.get("_pulse_phase", 0)
        ny = 0.15 + 0.10 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(lava_seg, f, "location", (lava_seg.location.x if f > 1 else lava_seg.location.x, ny, lava_seg.location.z if f > 1 else lava_seg.location.z))
        sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(lava_seg, f, "scale", (sc, 0.30, sc))

    # 50 sparks parabolic
    for sp_obj in sparks:
        bx_ = sp_obj["_base_x"]
        bz_ = sp_obj["_base_z"]
        ph = sp_obj["_phase"]
        spd = sp_obj["_speed"]
        local = (tt * spd + ph) % 1.0
        py = 0.3 + 5.0 * local * (1 - local)
        nx = bx_ * (1 + local * 0.5)
        nz = bz_ * (1 + local * 0.5)
        kf(sp_obj, f, "location", (nx, py, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 5 + ph * math.pi))
        kf(sp_obj, f, "scale", (sc, sc, sc))

    # 12 fragments drift + rotate
    for fr in fragments:
        bx_, by_, bz_ = fr["_base"]
        ph = fr["_phase"]
        ny = by_ + 0.5 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        nx = bx_ + 0.3 * math.cos(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(fr, f, "location", (nx, ny, bz_))
        kf(fr, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 6 ashes drift
    for ap in ashes:
        bx_, by_, bz_ = ap["_base"]
        ph = ap["_phase"]
        nx = bx_ + 0.6 * math.sin(2 * math.pi * tt * 0.4 + ph * math.pi)
        ny = by_ + 0.4 * math.cos(2 * math.pi * tt * 0.5 + ph * math.pi)
        kf(ap, f, "location", (nx, ny, bz_))
        sc = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi)
        kf(ap, f, "scale", (sc, 0.40, sc))

    # 8 fog drift
    for fp in fog_puffs:
        bx_, by_, bz_ = fp["_base"]
        ph = fp["_phase"]
        nx = bx_ + 0.8 * math.sin(2 * math.pi * tt * 0.3 + ph * math.pi)
        kf(fp, f, "location", (nx, by_, bz_))

    # 5 trees subtle sway
    for ti, tp in enumerate(trees_dead):
        sw = math.radians(3 * math.sin(2 * math.pi * tt * 0.6 + ti * 0.5))
        kf(tp, f, "rotation_euler", (sw, 0, math.radians(2 * math.cos(2 * math.pi * tt * 0.7 + ti * 0.4))))

    # sun mourant pulse
    sp = 1.0 + 0.06 * math.sin(2 * math.pi * tt * 1.5)
    kf(sun, f, "scale", (sp, sp, sp))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.12 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_phoenix_nest_rebirth] wrote {OUT}")
