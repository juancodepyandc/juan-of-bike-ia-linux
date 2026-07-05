"""
proc_giant_squid_battle.py — 171e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes + anatomie).

Calmar géant attaquant navire pirate :
- calmar géant anatomique : manteau + 2 nageoires + 8 bras + 2 tentacules longs + 2 yeux énormes + bec
- 8 bras propagated wave + 2 tentacules raptorial extended
- navire pirate (coque + 3 mâts + voiles + canon + drapeau)
- navire entouré tentacules (3 wrapped autour mâts)
- 6 marins jetés à l'eau
- 4 baleineaux fuyant
- ocean wave (50 segs)
- ciel tempête + 4 éclairs émissifs intermittent
- 15 pluie streaks
- 4 light beams sous-marins
- 30 bulles éclatant
- 20 fragments bois
- mouettes effrayées

Animations multi-axes simultanées :
- calmar manteau pulse + 8 bras wave propagated + 2 tentacules raptorial swing wide arcs
- navire roll + pitch + yaw rough sea
- 3 wrapping tentacles squeeze cyclic
- 4 éclairs intermittent intense
- 6 marins agitate
- 50 vagues wave
- 15 pluie streaks fall
- 30 bulles rise + 20 fragments drift

Sortie : output/3d/pbr_squid_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_squid_proc.glb"))

random.seed(0x509D14)


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
MAT_SKY = make_mat("sky_storm", (0.20, 0.18, 0.25), roughness=1.0, emi=(0.10, 0.10, 0.18), emi_strength=0.8)
MAT_CLOUD_DARK = make_mat("cloud_dark", (0.15, 0.13, 0.18), roughness=1.0, alpha=0.75, emi=(0.10, 0.08, 0.12), emi_strength=0.4)
MAT_LIGHTNING = make_mat("lightning", (1.0, 1.0, 0.85), roughness=0.0, emi=(1.0, 1.0, 0.85), emi_strength=25.0)
MAT_OCEAN = make_mat("ocean", (0.10, 0.18, 0.30), roughness=0.35, emi=(0.05, 0.10, 0.20), emi_strength=0.6)
MAT_WAVE_TOP = make_mat("wave_top", (0.50, 0.65, 0.80), roughness=0.10, alpha=0.85, emi=(0.30, 0.45, 0.65), emi_strength=1.5)
MAT_SQUID_BODY = make_mat("squid_body", (0.45, 0.15, 0.30), roughness=0.45, emi=(0.20, 0.05, 0.12), emi_strength=0.4)
MAT_SQUID_PALE = make_mat("squid_pale", (0.85, 0.55, 0.70), roughness=0.40, emi=(0.40, 0.25, 0.30), emi_strength=0.5)
MAT_SQUID_DARK = make_mat("squid_dark", (0.20, 0.08, 0.15), roughness=0.55)
MAT_SQUID_SUCKER = make_mat("squid_sucker", (1.0, 0.55, 0.65), roughness=0.20, emi=(0.55, 0.25, 0.30), emi_strength=0.7)
MAT_SQUID_EYE = make_mat("squid_eye", (1.0, 0.85, 0.20), roughness=0.0, emi=(1.0, 0.85, 0.20), emi_strength=14.0)
MAT_SQUID_BEAK = make_mat("squid_beak", (0.15, 0.10, 0.08), roughness=0.30, metallic=0.5)
MAT_SHIP_HULL = make_mat("ship_hull", (0.30, 0.18, 0.10), roughness=0.7)
MAT_SHIP_DECK = make_mat("ship_deck", (0.50, 0.32, 0.18), roughness=0.7)
MAT_SHIP_TRIM = make_mat("ship_trim", (0.85, 0.65, 0.30), metallic=0.6, roughness=0.35, emi=(0.30, 0.20, 0.08), emi_strength=0.4)
MAT_MAST = make_mat("mast", (0.20, 0.12, 0.06), roughness=0.85)
MAT_SAIL = make_mat("sail", (0.85, 0.78, 0.65), roughness=0.7, emi=(0.30, 0.28, 0.22), emi_strength=0.4)
MAT_SAIL_RIPPED = make_mat("sail_ripped", (0.65, 0.55, 0.45), roughness=0.7)
MAT_FLAG = make_mat("flag", (0.10, 0.05, 0.05), roughness=0.6)
MAT_CANNON = make_mat("cannon", (0.20, 0.18, 0.18), metallic=0.6, roughness=0.45)
MAT_SAILOR = make_mat("sailor", (0.55, 0.35, 0.20), roughness=0.6)
MAT_BUBBLE = make_mat("bubble", (0.80, 0.95, 1.0), roughness=0.05, alpha=0.45, emi=(0.55, 0.85, 1.0), emi_strength=1.5)
MAT_FRAGMENT = make_mat("fragment_wood", (0.45, 0.28, 0.15), roughness=0.7)
MAT_RAIN = make_mat("rain", (0.65, 0.80, 0.95), roughness=0.05, alpha=0.55, emi=(0.45, 0.65, 0.95), emi_strength=1.5)
MAT_SEAGULL = make_mat("seagull", (0.95, 0.92, 0.85), roughness=0.5)
MAT_LIGHT_BEAM = make_mat("light_beam", (0.55, 0.75, 1.0), roughness=0.0, alpha=0.15, emi=(0.55, 0.75, 1.0), emi_strength=2.0)


# --- backdrop : storm sky ----------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)

# 15 dark storm clouds
clouds = []
for ck in range(15):
    cx = random.uniform(-18, 18)
    cy = random.uniform(11, 15)
    cz = random.uniform(4, 12)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    for j in range(random.randint(3, 5)):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.8, 1.4), segs=14, rings=10, loc=(random.uniform(-1, 1), random.uniform(-0.2, 0.2), random.uniform(-0.7, 0.7)), parent=cp, mat=MAT_CLOUD_DARK, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.5, 0.9)

# 4 lightning bolts (intermittent intense)
lightnings = []
for lk in range(4):
    lx = random.uniform(-10, 10)
    lz = random.uniform(2, 8)
    lp = empty(f"lightning_{lk}_p", (lx, 8, lz))
    # zigzag lightning (5 segments)
    cur_y = 4
    cur_x = 0
    for sg in range(5):
        next_y = cur_y - 1.5
        next_x = cur_x + random.uniform(-0.3, 0.3)
        mx_avg = (cur_x + next_x) / 2
        my_avg = (cur_y + next_y) / 2
        dy = next_y - cur_y
        dx = next_x - cur_x
        length = math.sqrt(dx**2 + dy**2)
        angle = math.atan2(dy, dx)
        bolt = beveled_cube(f"lightning_{lk}_s_{sg}", (length, 0.15, 0.10), bevel_offset=0.03, bevel_segments=2, loc=(mx_avg, my_avg, 0), parent=lp, mat=MAT_LIGHTNING)
        bolt.rotation_euler = (0, 0, angle)
        cur_y = next_y
        cur_x = next_x
    lp["_phase"] = lk * 0.40
    lightnings.append(lp)


# --- ocean -------------------------------------------------------------
ocean_p = empty("ocean_p", (0, 0, 0))
ocean = beveled_cube("ocean", (40, 0.3, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=ocean_p, mat=MAT_OCEAN)

# 50 wave crests
wave_segs = []
for wk in range(50):
    wa = wk * (math.pi * 2 / 50)
    wr = random.uniform(5, 14)
    wx = math.cos(wa) * wr
    wz = math.sin(wa) * wr * 0.6
    if abs(wx) < 4 and abs(wz - 1) < 5:
        continue
    wseg = smooth_sphere(f"wave_{wk}", r=0.40, segs=14, rings=10, loc=(wx, 0.15, wz), parent=ocean_p, mat=MAT_WAVE_TOP, scale=(1.0, 0.30, 1.0))
    wseg["_base_y"] = 0.15
    wseg["_phase"] = wk * 0.20
    wave_segs.append(wseg)


# --- GIANT SQUID (left side, body submerged) ----------------------------
squid_p = empty("squid", (-4, 0.5, 0))

# mantle (body) — bullet-shaped
mantle = smooth_sphere("squid_mantle", r=1.5, segs=28, rings=22, loc=(0, 0.50, -1.5), parent=squid_p, mat=MAT_SQUID_BODY, scale=(1.0, 0.85, 2.5))
# pale belly highlight
smooth_sphere("squid_belly", r=1.2, segs=20, rings=14, loc=(0, -0.10, -1.5), parent=squid_p, mat=MAT_SQUID_PALE, scale=(1.0, 0.45, 2.4))
# 2 fins (triangular)
for fk, fz in [("L", 0.6), ("R", -0.6)]:
    fin_p = empty(f"squid_fin_{fk}_p", (0, 0.40, -2.8), parent=squid_p)
    smooth_sphere(f"squid_fin_{fk}", r=0.45, segs=18, rings=12, loc=(0, 0, fz), parent=fin_p, mat=MAT_SQUID_BODY, scale=(2.0, 0.10, 1.5))

# 2 huge eyes
for ek, ez in [("L", 0.7), ("R", -0.7)]:
    smooth_sphere(f"squid_eye_{ek}", r=0.30, segs=22, rings=16, loc=(0, 0.85, 0.50 + ez * 0.4), parent=squid_p, mat=MAT_SQUID_EYE)
    # eye iris dark
    smooth_sphere(f"squid_pupil_{ek}", r=0.12, segs=14, rings=10, loc=(0, 0.85, 0.70 + ez * 0.4), parent=squid_p, mat=MAT_SQUID_DARK)

# beak (between arms)
smooth_cone("squid_beak", r1=0.20, r2=0.10, depth=0.30, segs=10, loc=(0, 0.30, 1.0), parent=squid_p, mat=MAT_SQUID_BEAK)

# 8 ARMS (shorter) — propagating wave
squid_arms = []
ARM_OFFSETS = [(0.40, 0.20, 1.0), (0.20, 0.40, 1.1), (-0.20, 0.40, 1.1), (-0.40, 0.20, 1.0),
               (0.40, -0.10, 1.0), (0.20, -0.30, 1.1), (-0.20, -0.30, 1.1), (-0.40, -0.10, 1.0)]
for ak, base_pos in enumerate(ARM_OFFSETS):
    arm_root = empty(f"arm_{ak}_root", base_pos, parent=squid_p)
    # initial rotation outward
    spread_y = math.atan2(base_pos[0], base_pos[2])
    arm_root.rotation_euler = (math.radians(15), -spread_y, 0)
    # 6 segments wave
    arm_segs = []
    cur = arm_root
    for sg in range(6):
        e = empty(f"arm_{ak}_seg_p_{sg}", (0, 0, 0.40), parent=cur)
        rs = 0.18 - sg * 0.020
        smooth_sphere(f"arm_{ak}_s_{sg}", r=rs, segs=12, rings=8, loc=(0, 0, 0.20), parent=e, mat=MAT_SQUID_BODY, scale=(1.0, 1.0, 1.8))
        # 2 suckers per segment
        for su in range(2):
            sa = su * math.pi
            smooth_sphere(f"arm_{ak}_suck_{sg}_{su}", r=0.05, segs=8, rings=6, loc=(math.cos(sa) * 0.10, math.sin(sa) * 0.05, 0.20), parent=e, mat=MAT_SQUID_SUCKER)
        arm_segs.append(e)
        cur = e
    squid_arms.append({"root": arm_root, "segs": arm_segs, "k": ak})

# 2 LONG TENTACLES (raptorial) — extended for grabbing
long_tents = []
for tk, base_pos in [(0, (0.35, 0.15, 1.1)), (1, (-0.35, 0.15, 1.1))]:
    tent_root = empty(f"longt_{tk}_root", base_pos, parent=squid_p)
    spread_y = math.atan2(base_pos[0], base_pos[2])
    tent_root.rotation_euler = (math.radians(10), -spread_y, 0)
    # 12 long segments
    cur = tent_root
    segs = []
    for sg in range(12):
        e = empty(f"longt_{tk}_seg_p_{sg}", (0, 0, 0.45), parent=cur)
        rs = 0.10 - sg * 0.005
        smooth_sphere(f"longt_{tk}_s_{sg}", r=rs, segs=10, rings=8, loc=(0, 0, 0.22), parent=e, mat=MAT_SQUID_BODY, scale=(1.0, 1.0, 2.0))
        segs.append(e)
        cur = e
    # club at tip (large flattened)
    smooth_sphere(f"longt_{tk}_club", r=0.18, segs=14, rings=10, loc=(0, 0, 0.40), parent=cur, mat=MAT_SQUID_BODY, scale=(1.5, 1.0, 2.0))
    # 8 suckers on club
    for sk in range(8):
        sa = sk * (math.pi * 2 / 8)
        smooth_sphere(f"longt_{tk}_csk_{sk}", r=0.04, segs=8, rings=6, loc=(math.cos(sa) * 0.15, math.sin(sa) * 0.10, 0.45), parent=cur, mat=MAT_SQUID_SUCKER)
    long_tents.append({"root": tent_root, "segs": segs, "k": tk})


# --- PIRATE SHIP (right side) ------------------------------------------
ship_p = empty("ship", (3.5, 1.0, -1))
# hull (elongated)
smooth_sphere("ship_hull_main", r=1.2, segs=24, rings=18, loc=(0, 0, 0), parent=ship_p, mat=MAT_SHIP_HULL, scale=(2.5, 0.5, 0.95))
# hull bottom (V shape)
smooth_sphere("ship_hull_bot", r=0.85, segs=20, rings=14, loc=(0, -0.40, 0), parent=ship_p, mat=MAT_SHIP_HULL, scale=(2.7, 0.30, 0.55))
# deck
beveled_cube("ship_deck", (4.5, 0.10, 1.5), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.50, 0), parent=ship_p, mat=MAT_SHIP_DECK)
# stern (rear)
smooth_sphere("ship_stern", r=0.50, segs=18, rings=12, loc=(-2.0, 0.50, 0), parent=ship_p, mat=MAT_SHIP_HULL, scale=(1.0, 1.4, 1.0))
# bow figurehead (small)
smooth_sphere("ship_bow", r=0.40, segs=18, rings=12, loc=(2.2, 0.30, 0), parent=ship_p, mat=MAT_SHIP_TRIM, scale=(1.2, 1.0, 0.7))
# 3 masts
masts_pos = [-1.5, 0, 1.5]
for mi, mx in enumerate(masts_pos):
    smooth_cone(f"mast_{mi}", r1=0.10, r2=0.08, depth=4.0, segs=10, loc=(mx, 2.5, 0), parent=ship_p, mat=MAT_MAST)
    # cross-beam yard
    beveled_cube(f"yard_{mi}_top", (0.05, 0.05, 2.2), bevel_offset=0.01, bevel_segments=2, loc=(mx, 4.0, 0), parent=ship_p, mat=MAT_MAST)
    beveled_cube(f"yard_{mi}_mid", (0.05, 0.05, 1.8), bevel_offset=0.01, bevel_segments=2, loc=(mx, 3.0, 0), parent=ship_p, mat=MAT_MAST)
    # sails (1 top + 1 mid, some ripped)
    if mi != 1:  # central mast sail intact, others damaged
        smooth_sphere(f"sail_{mi}_top", r=0.50, segs=14, rings=8, loc=(mx, 3.7, 0), parent=ship_p, mat=MAT_SAIL, scale=(0.04, 0.7, 1.6))
        smooth_sphere(f"sail_{mi}_mid", r=0.50, segs=14, rings=8, loc=(mx, 2.7, 0), parent=ship_p, mat=MAT_SAIL_RIPPED, scale=(0.04, 0.7, 1.4))
# flag (pirate)
flag_p = empty("flag_p", (-1.5, 4.5, 0), parent=ship_p)
beveled_cube("flag", (0.04, 0.30, 0.50), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.25), parent=flag_p, mat=MAT_FLAG)

# 2 cannons on deck
for ck, cx in [(0, -1), (1, 1)]:
    cp = empty(f"cannon_{ck}_p", (cx, 0.70, 0.70), parent=ship_p)
    smooth_cone(f"cannon_{ck}", r1=0.12, r2=0.08, depth=0.85, segs=12, loc=(0, 0, 0), parent=cp, mat=MAT_CANNON)
    cp.rotation_euler = (math.radians(90), 0, 0)


# --- 3 WRAPPING TENTACLES (around ship masts) ------------------------
wrap_tents = []
for wt in range(3):
    wt_p = empty(f"wraptent_{wt}_p", (-4, 1.0, 0))
    # 8 segments arc up to ship mast
    target_x = -1.5 + wt * 1.5 + 3.5
    target_y = 3.0
    cur = wt_p
    for sg in range(10):
        progress = sg / 9
        x_pos = -4 + (target_x - (-4)) * progress + 0.5 * math.sin(progress * math.pi * 2)
        y_pos = 0.5 + (target_y - 0.5) * progress + 1.5 * math.sin(progress * math.pi)
        e = empty(f"wraptent_{wt}_e_{sg}", (0, 0, 0), parent=cur)
        smooth_sphere(f"wraptent_{wt}_s_{sg}", r=0.15 - sg * 0.008, segs=12, rings=8, loc=(x_pos - (cur.location.x if hasattr(cur, 'location') else 0), y_pos - (cur.location.y if hasattr(cur, 'location') else 0), 0), parent=e, mat=MAT_SQUID_BODY)
        cur = e
    wrap_tents.append({"p": wt_p, "phase": wt * 0.4})


# --- 6 sailors in water --------------------------------------------------
sailors = []
for sa in range(6):
    sx = random.uniform(2, 7)
    sz = random.uniform(-2, 2)
    sp = empty(f"sailor_{sa}_p", (sx, 0.50, sz))
    sailors.append(sp)
    # head
    smooth_sphere(f"sailor_{sa}_head", r=0.18, segs=14, rings=10, loc=(0, 0, 0), parent=sp, mat=MAT_SAILOR)
    # 2 arms raised
    for ak, az in [("L", 0.10), ("R", -0.10)]:
        arm = smooth_cone(f"sailor_{sa}_arm_{ak}", r1=0.04, r2=0.04, depth=0.30, segs=6, loc=(0.15, 0.18, az), parent=sp, mat=MAT_SAILOR)
        arm.rotation_euler = (0, 0, math.radians(-45))
    sp["_base"] = (sx, 0.50, sz)
    sp["_phase"] = sa * 0.30


# --- 30 bubbles éclatant ----------------------------------------------
bubbles = []
for bk in range(30):
    bx = random.uniform(-7, 7)
    by = random.uniform(0.2, 1.5)
    bz = random.uniform(-3, 4)
    bu = smooth_sphere(f"bubble_{bk}", r=random.uniform(0.06, 0.12), segs=10, rings=6, loc=(bx, by, bz), mat=MAT_BUBBLE)
    bu["_base"] = (bx, by, bz)
    bu["_phase"] = bk * 0.20
    bu["_speed"] = random.uniform(1.2, 2.2)
    bubbles.append(bu)


# --- 20 wood fragments drift -----------------------------------------
fragments = []
for fk in range(20):
    fx = random.uniform(-6, 6)
    fz = random.uniform(-3, 3)
    fp = beveled_cube(f"frag_{fk}", (random.uniform(0.20, 0.40), random.uniform(0.08, 0.15), random.uniform(0.15, 0.30)), bevel_offset=0.02, bevel_segments=2, loc=(fx, 0.30, fz), mat=MAT_FRAGMENT)
    fp["_base"] = (fx, 0.30, fz)
    fp["_phase"] = fk * 0.15
    fragments.append(fp)


# --- 15 rain streaks -----------------------------------------------
rain_streaks = []
for rk in range(15):
    rx = random.uniform(-12, 12)
    ry = random.uniform(4, 10)
    rz = random.uniform(0, 6)
    rs = beveled_cube(f"rain_{rk}", (0.05, 0.50, 0.05), bevel_offset=0.01, bevel_segments=2, loc=(rx, ry, rz), mat=MAT_RAIN)
    rs.rotation_euler = (0, 0, math.radians(-10))
    rs["_base"] = (rx, ry, rz)
    rs["_phase"] = rk * 0.10
    rain_streaks.append(rs)


# --- 6 seagulls effrayées -----------------------------------------
seagulls = []
for sk in range(6):
    a = sk * (math.pi * 2 / 6) + 0.3
    r = random.uniform(8, 13)
    sy = random.uniform(7, 11)
    sp = empty(f"sg_{sk}_p", (math.cos(a) * r, sy, math.sin(a) * r * 0.7))
    smooth_sphere(f"sg_{sk}_b", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=sp, mat=MAT_SEAGULL, scale=(1.4, 0.7, 0.7))
    wL = empty(f"sg_{sk}_wL", (0, 0.02, 0.05), parent=sp)
    wR = empty(f"sg_{sk}_wR", (0, 0.02, -0.05), parent=sp)
    smooth_sphere(f"sg_{sk}_wL_b", r=0.10, segs=10, rings=6, loc=(0, 0, 0.15), parent=wL, mat=MAT_SEAGULL, scale=(0.5, 0.05, 1.5))
    smooth_sphere(f"sg_{sk}_wR_b", r=0.10, segs=10, rings=6, loc=(0, 0, -0.15), parent=wR, mat=MAT_SEAGULL, scale=(0.5, 0.05, 1.5))
    seagulls.append({"p": sp, "wL": wL, "wR": wR, "a": a, "r": r, "sy": sy, "phase": sk * 0.35})


# --- 4 light beams sous-marins ----------------------------------------
for bk in range(4):
    bx = random.uniform(-8, 8)
    bz = random.uniform(-3, 5)
    beam = beveled_cube(f"beam_{bk}", (0.40, 8, 0.40), bevel_offset=0.04, bevel_segments=2, loc=(bx, 4, bz), mat=MAT_LIGHT_BEAM)
    beam.rotation_euler = (math.radians(random.uniform(-5, 5)), 0, math.radians(random.uniform(-8, 8)))


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

    # squid body sway + pulse
    sy = 0.5 + 0.30 * math.sin(2 * math.pi * tt * 0.8)
    kf(squid_p, f, "location", (-4 + 0.5 * math.sin(2 * math.pi * tt * 0.5), sy, 0))
    kf(squid_p, f, "rotation_euler", (math.radians(5 * math.sin(2 * math.pi * tt * 1.0)), math.radians(15 * math.sin(2 * math.pi * tt * 0.6)), 0))
    # mantle pulse
    ms = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2)
    kf(mantle, f, "scale", (ms, 0.85 * (1 - 0.04 * math.sin(2 * math.pi * tt * 2)), 2.5 * ms))

    # 8 arms wave propagated
    for ad in squid_arms:
        ak = ad["k"]
        # base phase per arm
        base_phase = ak * 0.5
        for si, seg in enumerate(ad["segs"]):
            wave_x = math.radians(20) * math.sin(2 * math.pi * tt * 2.5 + base_phase - si * 0.5)
            wave_y = math.radians(15) * math.cos(2 * math.pi * tt * 2.2 + base_phase - si * 0.4)
            kf(seg, f, "rotation_euler", (wave_x, wave_y, 0))

    # 2 long tentacles : raptorial wide swings
    for td in long_tents:
        tk = td["k"]
        side = 1 if tk == 0 else -1
        for si, seg in enumerate(td["segs"]):
            # propagated wide arc
            wave = math.radians(15) * math.sin(2 * math.pi * tt * 1.5 - si * 0.3)
            wave_y = math.radians(10) * math.cos(2 * math.pi * tt * 1.3 - si * 0.2) * side
            kf(seg, f, "rotation_euler", (wave, wave_y, 0))

    # 3 wrapping tentacles squeeze cyclic
    for wt in wrap_tents:
        ph = wt["phase"]
        squeeze = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(wt["p"], f, "scale", (squeeze, squeeze, squeeze))

    # ship roll + pitch + yaw rough sea
    sb_x = 3.5 + 0.3 * math.sin(2 * math.pi * tt * 0.5)
    sb_y = 1.0 + 0.4 * math.cos(2 * math.pi * tt * 0.7)
    kf(ship_p, f, "location", (sb_x, sb_y, -1))
    roll = math.radians(20 * math.sin(2 * math.pi * tt * 0.6))
    pitch = math.radians(15 * math.sin(2 * math.pi * tt * 0.8))
    yaw = math.radians(10 * math.sin(2 * math.pi * tt * 0.4))
    kf(ship_p, f, "rotation_euler", (pitch, yaw, roll))
    # flag
    kf(flag_p, f, "rotation_euler", (math.radians(15 * math.sin(2 * math.pi * tt * 3)), 0, math.radians(10 * math.cos(2 * math.pi * tt * 4))))

    # 4 lightning intermittent (peaks ~3 times)
    for li, lp in enumerate(lightnings):
        ph = lp["_phase"]
        # active at certain windows
        cycle = (tt + ph) % 0.33
        intensity = 1.0 if cycle < 0.04 else 0.0
        sc = 0.1 + intensity * 1.5
        kf(lp, f, "scale", (sc, sc, sc))

    # 50 waves
    for ws in wave_segs:
        ph = ws["_phase"]
        ny = ws["_base_y"] + 0.30 * math.sin(2 * math.pi * tt * 2.0 + ph * math.pi)
        kf(ws, f, "location", (ws.location.x if f > 1 else ws.location.x, ny, ws.location.z if f > 1 else ws.location.z))
        sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(ws, f, "scale", (sc, 0.30, sc))

    # 6 sailors agitate
    for sl in sailors:
        bx_, by_, bz_ = sl["_base"]
        ph = sl["_phase"]
        nx = bx_ + 0.20 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        ny = by_ + 0.15 * math.cos(2 * math.pi * tt * 2 + ph * math.pi)
        nz = bz_ + 0.15 * math.sin(2 * math.pi * tt * 1.7 + ph * math.pi)
        kf(sl, f, "location", (nx, ny, nz))
        kf(sl, f, "rotation_euler", (0, math.radians(180 * tt + ph * 60), 0))

    # 30 bubbles
    for bu in bubbles:
        bx_, by_, bz_ = bu["_base"]
        ph = bu["_phase"]
        spd = bu["_speed"]
        local = (tt * spd + ph) % 1.0
        ny = by_ + local * 9
        nx = bx_ + 0.20 * math.sin(2 * math.pi * local * 5 + ph)
        kf(bu, f, "location", (nx, ny, bz_))
        sc = 0.7 + local * 0.5
        kf(bu, f, "scale", (sc, sc, sc))

    # 20 fragments drift + rotate
    for fr in fragments:
        bx_, by_, bz_ = fr["_base"]
        ph = fr["_phase"]
        nx = bx_ + 0.30 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        ny = by_ + 0.20 * math.cos(2 * math.pi * tt * 1.0 + ph * math.pi)
        kf(fr, f, "location", (nx, ny, bz_))
        kf(fr, f, "rotation_euler", (math.radians(120 * tt + ph * 30), math.radians(80 * tt + ph * 40), math.radians(60 * tt + ph * 20)))

    # 15 rain streaks fall
    for ri, rs in enumerate(rain_streaks):
        bx_, by_, bz_ = rs["_base"]
        ph = rs["_phase"]
        local = (tt * 3 + ph) % 1.0
        ny = by_ - local * 9
        if ny < 0:
            ny += 10
        kf(rs, f, "location", (bx_, ny, bz_))

    # 6 seagulls flap + erratic
    for sg in seagulls:
        ang = sg["a"] + tt * 2 * math.pi * 0.5 + 0.3 * math.sin(2 * math.pi * tt * 3 + sg["phase"])
        bx_ = math.cos(ang) * sg["r"]
        bz_ = math.sin(ang) * sg["r"] * 0.7
        by_ = sg["sy"] + 0.4 * math.sin(2 * math.pi * tt * 1.5 + sg["phase"])
        kf(sg["p"], f, "location", (bx_, by_, bz_))
        kf(sg["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(55) * math.sin(2 * math.pi * tt * 10 + sg["phase"])
        kf(sg["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(sg["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 15 clouds drift
    for cp in clouds:
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 6 - 3
        if new_x > 18:
            new_x -= 36
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_giant_squid_battle] wrote {OUT}")
