"""
proc_titanic_ocean_liner.py — 186e procédural AuroraIA, MILESTONE 50E QUALITÉ.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Titanic transatlantique géant :
- coque massive (3 sections échelonnées)
- 4 cheminées massives + fumée intense
- 300 hublots émissifs en lignes illuminées
- 6 ponts superposés
- 6 canots sauvetage
- 4 mâts + drapeau + pavillon
- ancre énorme
- bridge cockpit avant
- 2 hélices arrière spin
- sillage écumeux
- ciel nuit étoilée + lune
- ocean ondulant + 30 vagues
- 4 mouettes
- reflets eau

Animations multi-axes simultanées :
- Titanic drift slow forward + roll/pitch légèrement
- 4 cheminées smoke rise cyclique
- 300 hublots cycle pulse
- 2 hélices spin Y continu
- sillage écumeux trail
- 30 ocean waves
- 4 mouettes orbit + flap

Sortie : output/3d/pbr_titanic_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_titanic_proc.glb"))

random.seed(0x717A17)


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
MAT_SKY_NIGHT = make_mat("sky_night", (0.05, 0.08, 0.18), roughness=1.0, emi=(0.04, 0.06, 0.15), emi_strength=0.5)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.5)
MAT_MOON = make_mat("moon", (0.95, 0.92, 0.85), roughness=0.0, emi=(0.95, 0.92, 0.85), emi_strength=8.0)
MAT_MOON_HALO = make_mat("moon_halo", (0.95, 0.92, 0.85), roughness=0.0, alpha=0.30, emi=(0.95, 0.92, 0.85), emi_strength=2.5)
MAT_OCEAN = make_mat("ocean_night", (0.05, 0.10, 0.20), roughness=0.30, emi=(0.04, 0.08, 0.18), emi_strength=0.6)
MAT_WAVE_TOP = make_mat("wave_top", (0.30, 0.45, 0.65), roughness=0.10, alpha=0.85, emi=(0.20, 0.30, 0.50), emi_strength=1.0)
MAT_HULL = make_mat("hull_black", (0.06, 0.06, 0.08), roughness=0.7, emi=(0.03, 0.03, 0.05), emi_strength=0.2)
MAT_HULL_WHITE = make_mat("hull_white", (0.92, 0.90, 0.85), roughness=0.6, emi=(0.40, 0.38, 0.35), emi_strength=0.5)
MAT_HULL_GOLD = make_mat("hull_gold", (0.95, 0.75, 0.30), metallic=0.7, roughness=0.30, emi=(0.30, 0.22, 0.08), emi_strength=0.5)
MAT_DECK = make_mat("deck_wood", (0.45, 0.25, 0.12), roughness=0.7)
MAT_CHIMNEY = make_mat("chimney", (0.85, 0.65, 0.20), roughness=0.50, emi=(0.30, 0.22, 0.08), emi_strength=0.4)
MAT_CHIMNEY_TOP = make_mat("chimney_top", (0.20, 0.15, 0.10), roughness=0.85)
MAT_HUBLOT = make_mat("hublot", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=12.0)
MAT_HUBLOT_FRAME = make_mat("hublot_frame", (0.45, 0.40, 0.35), metallic=0.6, roughness=0.40)
MAT_SMOKE = make_mat("smoke", (0.30, 0.28, 0.32), roughness=1.0, alpha=0.45, emi=(0.18, 0.16, 0.20), emi_strength=0.7)
MAT_MAST = make_mat("mast", (0.40, 0.30, 0.18), roughness=0.7)
MAT_FLAG = make_mat("flag", (0.85, 0.20, 0.15), roughness=0.6, emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_ROPE = make_mat("rope", (0.55, 0.45, 0.30), roughness=0.8)
MAT_ANCHOR = make_mat("anchor", (0.30, 0.28, 0.28), metallic=0.85, roughness=0.45)
MAT_BRIDGE = make_mat("bridge_cab", (0.85, 0.85, 0.80), roughness=0.5, emi=(0.40, 0.40, 0.38), emi_strength=0.4)
MAT_LIFEBOAT = make_mat("lifeboat", (0.85, 0.80, 0.65), roughness=0.6, emi=(0.30, 0.28, 0.22), emi_strength=0.3)
MAT_PROPELLER = make_mat("propeller", (0.85, 0.65, 0.30), metallic=0.85, roughness=0.30, emi=(0.30, 0.22, 0.08), emi_strength=0.5)
MAT_WAKE = make_mat("wake", (0.85, 0.95, 1.0), roughness=0.10, alpha=0.55, emi=(0.65, 0.85, 1.0), emi_strength=2.0)
MAT_SEAGULL = make_mat("seagull", (0.85, 0.85, 0.80), roughness=0.5, emi=(0.30, 0.30, 0.28), emi_strength=0.3)


# --- backdrop : night sky -----------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY_NIGHT)
# 80 stars
for i in range(80):
    smooth_sphere(f"star_{i}", r=random.uniform(0.06, 0.12), segs=10, rings=8, loc=(random.uniform(-22, 22), random.uniform(11, 16), random.uniform(8, 16)), mat=MAT_STAR)
# moon + halo
moon_p = empty("moon_p", (10, 14, 10))
smooth_sphere("moon", r=1.4, segs=24, rings=18, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON)
moon_halo = smooth_sphere("moon_halo", r=2.3, segs=22, rings=14, loc=(0, 0, 0), parent=moon_p, mat=MAT_MOON_HALO)


# --- ocean -------------------------------------------------------------
ocean_p = empty("ocean", (0, 0, 0))
ocean = beveled_cube("ocean", (40, 0.3, 25), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 2), parent=ocean_p, mat=MAT_OCEAN)

# 30 wave crests
wave_segs = []
for wk in range(30):
    a = wk * (math.pi * 2 / 30)
    r = random.uniform(8, 14)
    wx = math.cos(a) * r
    wz = math.sin(a) * r * 0.6
    if abs(wx) < 8 and abs(wz - 1) < 3:
        continue  # skip near ship
    wseg = smooth_cone(f"wave_{wk}", r1=0.40, r2=0.30, depth=0.15, segs=14, loc=(wx, 0.10, wz), parent=ocean_p, mat=MAT_WAVE_TOP)
    wseg.rotation_euler = (math.radians(90), 0, 0)
    wseg["_phase"] = wk * 0.20
    wave_segs.append(wseg)


# --- TITANIC paquebot géant -------------------------------------------
ship_p = empty("titanic", (0, 1.5, 0))

# COQUE MAIN (3 sections échelonnées for tapering)
# main hull
beveled_cube("hull_main", (10, 2.0, 1.6), bevel_offset=0.10, bevel_segments=3, loc=(0, 0, 0), parent=ship_p, mat=MAT_HULL)
# bow (front pointed)
smooth_cone("hull_bow", r1=0.0, r2=1.0, depth=2.5, segs=12, loc=(6.0, 0, 0), parent=ship_p, mat=MAT_HULL)
bp = bpy.data.objects.get("hull_bow")
if bp:
    bp.rotation_euler = (0, 0, math.radians(-90))
# stern (back rounded)
smooth_sphere("hull_stern", r=1.0, segs=20, rings=14, loc=(-5.5, 0, 0), parent=ship_p, mat=MAT_HULL, scale=(1.2, 1.0, 1.6))
# bottom V keel
smooth_sphere("hull_keel", r=0.55, segs=18, rings=12, loc=(0, -1.10, 0), parent=ship_p, mat=MAT_HULL, scale=(15, 0.30, 1.4))
# upper section
beveled_cube("hull_upper", (9, 0.85, 1.4), bevel_offset=0.08, bevel_segments=2, loc=(0, 1.40, 0), parent=ship_p, mat=MAT_HULL_WHITE)
# decorative gold band
beveled_cube("hull_band", (10, 0.10, 1.65), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.00, 0), parent=ship_p, mat=MAT_HULL_GOLD)

# 6 PONTS (decks) superposés
for dk in range(6):
    dy = 2.0 + dk * 0.45
    dw = 8 - dk * 0.5
    dd = 1.4 - dk * 0.10
    beveled_cube(f"deck_{dk}", (dw, 0.30, dd), bevel_offset=0.04, bevel_segments=2, loc=(0, dy, 0), parent=ship_p, mat=MAT_HULL_WHITE)
    # gold trim
    beveled_cube(f"deck_{dk}_trim", (dw, 0.05, dd + 0.05), bevel_offset=0.02, bevel_segments=2, loc=(0, dy - 0.20, 0), parent=ship_p, mat=MAT_HULL_GOLD)

# 4 CHEMINÉES massives (signature Titanic)
chimneys = []
for ck, cx in enumerate([-2.5, -0.8, 0.8, 2.5]):
    chim_p = empty(f"chim_{ck}_p", (cx, 4.5, 0), parent=ship_p)
    chimneys.append({"p": chim_p, "phase": ck * 0.25})
    # body
    smooth_cone(f"chim_{ck}_body", r1=0.50, r2=0.45, depth=2.5, segs=14, loc=(0, 1.25, 0), parent=chim_p, mat=MAT_CHIMNEY)
    # tilted slightly back (signature)
    cb = bpy.data.objects.get(f"chim_{ck}_body")
    if cb:
        cb.rotation_euler = (0, 0, math.radians(8))
    # top dark rim
    smooth_cone(f"chim_{ck}_top", r1=0.50, r2=0.50, depth=0.15, segs=14, loc=(0, 2.50, 0), parent=chim_p, mat=MAT_CHIMNEY_TOP)
    # 3 smoke puffs (parented to chimney top)
    smokes = []
    for sk in range(3):
        sp = smooth_sphere(f"chim_{ck}_smoke_{sk}", r=0.40, segs=14, rings=10, loc=(0, 3.0 + sk * 0.60, 0), parent=chim_p, mat=MAT_SMOKE, scale=(1.2, 1.0, 1.2))
        sp["_phase"] = sk * 0.33
        smokes.append(sp)
    chimneys[ck]["smokes"] = smokes

# 300 HUBLOTS émissifs en lignes (signature illumination)
# 3 lines of hublots × 100 each side × 2 sides = ~600 if we go too dense, let's do 3×50 per side = 150 each, 300 total
hublots = []
for side in [-1, 1]:
    for li in range(3):
        ly = 0.5 + li * 0.5  # 3 vertical lines
        for ki in range(50):
            kx = -4.8 + ki * 0.19
            if abs(kx) > 5:
                continue
            hub = smooth_sphere(f"hublot_{side}_{li}_{ki}", r=0.05, segs=8, rings=6, loc=(kx, ly, side * 0.82), parent=ship_p, mat=MAT_HUBLOT)
            hub["_phase"] = (li * 50 + ki) * 0.08
            hublots.append(hub)

# BRIDGE COCKPIT (avant)
bridge_p = empty("bridge_p", (3.5, 3.5, 0), parent=ship_p)
beveled_cube("bridge_body", (1.2, 0.60, 1.0), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=bridge_p, mat=MAT_BRIDGE)
# 4 windows
for wk in range(4):
    wx = -0.40 + wk * 0.27
    smooth_sphere(f"bridge_win_{wk}", r=0.08, segs=10, rings=6, loc=(wx, 0.10, 0.51), parent=bridge_p, mat=MAT_HUBLOT, scale=(1.0, 1.5, 0.30))

# 4 MÂTS
for mk, mx in [(0, 5.0), (1, -2.0), (2, 2.0), (3, -5.0)]:
    mast_p = empty(f"mast_{mk}_p", (mx, 5.0, 0), parent=ship_p)
    smooth_cone(f"mast_{mk}_body", r1=0.08, r2=0.04, depth=2.5, segs=8, loc=(0, 1.25, 0), parent=mast_p, mat=MAT_MAST)
    # crow's nest top (small)
    smooth_sphere(f"mast_{mk}_nest", r=0.12, segs=10, rings=8, loc=(0, 2.0, 0), parent=mast_p, mat=MAT_DECK)
    # 3 cables radial
    for ck in range(3):
        ca = ck * (math.pi * 2 / 3)
        smooth_cone(f"mast_{mk}_cable_{ck}", r1=0.012, r2=0.012, depth=1.5, segs=4, loc=(math.cos(ca) * 0.30, 1.0, math.sin(ca) * 0.30), parent=mast_p, mat=MAT_ROPE)
# main flag on first mast
flag_p = empty("flag_p", (5.0, 7.2, 0), parent=ship_p)
beveled_cube("flag", (0.04, 0.50, 0.80), bevel_offset=0.03, bevel_segments=2, loc=(0, 0, 0.40), parent=flag_p, mat=MAT_FLAG)

# 6 CANOTS sauvetage (3 each side)
for li in range(6):
    side = -1 if li < 3 else 1
    lx = -2.5 + (li % 3) * 2.0
    boat_p = empty(f"lifeboat_{li}_p", (lx, 3.0, side * 0.9), parent=ship_p)
    # body (elongated)
    smooth_sphere(f"lifeboat_{li}_body", r=0.30, segs=14, rings=10, loc=(0, 0, 0), parent=boat_p, mat=MAT_LIFEBOAT, scale=(2.0, 0.35, 0.85))
    # davits (small cranes)
    for dk in range(2):
        smooth_cone(f"lifeboat_{li}_davit_{dk}", r1=0.04, r2=0.03, depth=0.45, segs=6, loc=(-0.25 + dk * 0.5, 0.25, 0), parent=boat_p, mat=MAT_MAST)

# ANCRE énorme (avant)
anchor_p = empty("anchor_p", (5.8, 0.5, 0.9), parent=ship_p)
# chain (3 segs)
for ck in range(3):
    smooth_sphere(f"anchor_chain_{ck}", r=0.10, segs=10, rings=6, loc=(0, -ck * 0.30, 0), parent=anchor_p, mat=MAT_ANCHOR, scale=(1.0, 0.6, 1.0))
# main body
smooth_cone("anchor_body", r1=0.20, r2=0.30, depth=0.50, segs=10, loc=(0, -1.0, 0), parent=anchor_p, mat=MAT_ANCHOR)
# 2 arms
for ak, az in [(0, 0.25), (1, -0.25)]:
    arm = smooth_cone(f"anchor_arm_{ak}", r1=0.10, r2=0.0, depth=0.40, segs=8, loc=(0, -1.10, az), parent=anchor_p, mat=MAT_ANCHOR)
    arm.rotation_euler = (math.radians(45 if az > 0 else -45), 0, 0)

# 2 HÉLICES arrière + axe + spin
propellers = []
for pk, pz in [(0, 0.45), (1, -0.45)]:
    prop_p = empty(f"prop_{pk}_p", (-6.0, -0.50, pz), parent=ship_p)
    propellers.append({"p": prop_p, "phase": pk * 0.40})
    # axe
    smooth_cone(f"prop_{pk}_axe", r1=0.06, r2=0.06, depth=0.40, segs=8, loc=(0.20, 0, 0), parent=prop_p, mat=MAT_HULL_GOLD)
    pa = bpy.data.objects.get(f"prop_{pk}_axe")
    if pa:
        pa.rotation_euler = (0, 0, math.radians(90))
    # 4 blades
    for bk in range(4):
        ba = bk * (math.pi * 2 / 4)
        blade = beveled_cube(f"prop_{pk}_b_{bk}", (0.04, 0.30, 0.10), bevel_offset=0.01, bevel_segments=2, loc=(math.cos(ba) * 0.15, math.sin(ba) * 0.15, 0), parent=prop_p, mat=MAT_PROPELLER)
        blade.rotation_euler = (0, 0, ba)
    # hub
    smooth_sphere(f"prop_{pk}_hub", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=prop_p, mat=MAT_HULL_GOLD)

# SILLAGE écumeux (wake trail behind ship)
wake_segs = []
for wk in range(15):
    wx = -7 - wk * 1.0
    wy = 0.15
    wz_off = math.sin(wk * 0.3) * 0.3
    wseg = beveled_cube(f"wake_{wk}", (1.5, 0.10, 0.85), bevel_offset=0.04, bevel_segments=2, loc=(wx, wy, wz_off), mat=MAT_WAKE)
    wseg["_phase"] = wk * 0.15
    wake_segs.append(wseg)


# --- 4 MOUETTES volant -----------------------------------------------
seagulls = []
for sk in range(4):
    a = sk * (math.pi * 2 / 4) + 0.5
    r = random.uniform(7, 11)
    sy = random.uniform(6, 10)
    sp = empty(f"sg_{sk}_p", (math.cos(a) * r, sy, math.sin(a) * r * 0.7))
    seagulls.append({"p": sp, "a": a, "r": r, "sy": sy, "phase": sk * 0.40})
    # body
    smooth_sphere(f"sg_{sk}_body", r=0.10, segs=12, rings=8, loc=(0, 0, 0), parent=sp, mat=MAT_SEAGULL, scale=(1.4, 0.7, 0.7))
    # 2 wings
    wL = empty(f"sg_{sk}_wL", (0, 0.02, 0.05), parent=sp)
    wR = empty(f"sg_{sk}_wR", (0, 0.02, -0.05), parent=sp)
    smooth_sphere(f"sg_{sk}_wL_b", r=0.10, segs=10, rings=6, loc=(0, 0, 0.15), parent=wL, mat=MAT_SEAGULL, scale=(0.5, 0.05, 1.5))
    smooth_sphere(f"sg_{sk}_wR_b", r=0.10, segs=10, rings=6, loc=(0, 0, -0.15), parent=wR, mat=MAT_SEAGULL, scale=(0.5, 0.05, 1.5))
    seagulls[sk]["wL"] = wL
    seagulls[sk]["wR"] = wR


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

    # TITANIC drift slow forward + roll/pitch
    ship_x = 0 + tt * 1.5
    ship_y = 1.5 + 0.15 * math.sin(2 * math.pi * tt * 0.5)
    kf(ship_p, f, "location", (ship_x, ship_y, 0))
    roll = math.radians(2 * math.sin(2 * math.pi * tt * 0.6))
    pitch = math.radians(1.5 * math.cos(2 * math.pi * tt * 0.8))
    kf(ship_p, f, "rotation_euler", (pitch, 0, roll))

    # 4 cheminées smoke rise
    for ch in chimneys:
        for sp_st in ch["smokes"]:
            ph = sp_st["_phase"]
            local = (tt * 1.2 + ph) % 1.0
            ny = 3.0 + local * 2.5
            sc = 1.0 + local * 1.4
            kf(sp_st, f, "location", (0, ny, 0))
            kf(sp_st, f, "scale", (sc, sc, sc))

    # 300 hublots cycle pulse
    for hub in hublots:
        ph = hub["_phase"]
        ps = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(hub, f, "scale", (ps, ps, ps))

    # 2 hélices spin
    for pr in propellers:
        ph = pr["phase"]
        kf(pr["p"], f, "rotation_euler", (math.radians(360 * tt * 12 + ph * 90), 0, 0))

    # 15 wake segments : trail + pulse
    for wk_seg in wake_segs:
        ph = wk_seg["_phase"]
        sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(wk_seg, f, "scale", (sc, 1.0, sc))

    # 30 ocean waves
    for ws in wave_segs:
        ph = ws["_phase"]
        ny = 0.10 + 0.20 * math.sin(2 * math.pi * tt * 2 + ph * math.pi)
        kf(ws, f, "location", (ws.location.x if f > 1 else ws.location.x, ny, ws.location.z if f > 1 else ws.location.z))
        sc = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(ws, f, "scale", (sc, 1.0, sc))

    # 4 seagulls orbit + flap
    for sg in seagulls:
        ang = sg["a"] + tt * 2 * math.pi * 0.3
        bx_ = math.cos(ang) * sg["r"]
        bz_ = math.sin(ang) * sg["r"] * 0.7
        by_ = sg["sy"] + 0.3 * math.sin(2 * math.pi * tt * 1.5 + sg["phase"])
        kf(sg["p"], f, "location", (bx_, by_, bz_))
        kf(sg["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(50) * math.sin(2 * math.pi * tt * 8 + sg["phase"])
        kf(sg["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(sg["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # moon halo breathe
    mh = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 1.3)
    kf(moon_halo, f, "scale", (mh, mh, mh))

    # flag wave
    kf(flag_p, f, "rotation_euler", (math.radians(15 * math.sin(2 * math.pi * tt * 3)), 0, math.radians(8 * math.cos(2 * math.pi * tt * 4))))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_titanic_ocean_liner] wrote {OUT}")
