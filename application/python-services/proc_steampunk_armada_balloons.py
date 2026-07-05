"""
proc_steampunk_armada_balloons.py — 179e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Armada montgolfières steampunk en vol :
- 8 montgolfières steampunk (ballon métal + nacelle bois + 2 brûleurs + propeller + 2 canons + drapeau)
- 5 dirigeables petits avec gondoles
- 30 plates-formes flottantes en construction
- ville volante centrale (3 tours métal + ponts)
- 50 étincelles + 12 fragments
- nuages denses 15
- ciel orange steampunk
- soleil émissif
- grues mobiles
- 8 oiseaux mécaniques

Animations multi-axes simultanées :
- 8 montgolfières flottent indépendamment (Y bob différentielle + sway + roll)
- brûleurs flammes pulse intenses
- propellers spin
- canons recoil cyclic
- drapeaux flutter
- 5 dirigeables drift indépendantes
- 30 plates rotate Y subtle
- 50 étincelles parabolic
- nuages drift
- soleil pulse
- 8 birds mécaniques flap + orbit

Sortie : output/3d/pbr_armada_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_armada_proc.glb"))

random.seed(0xA2A4DA)


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
MAT_SKY = make_mat("sky_steampunk", (0.85, 0.50, 0.25), roughness=1.0, emi=(0.65, 0.35, 0.20), emi_strength=1.0)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=12.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.85, 0.40), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.40), emi_strength=3.0)
MAT_CLOUD = make_mat("cloud", (0.90, 0.78, 0.65), roughness=1.0, alpha=0.65, emi=(0.50, 0.40, 0.32), emi_strength=0.4)
MAT_BALLOON_BRASS = make_mat("balloon_brass", (0.85, 0.65, 0.30), metallic=0.85, roughness=0.30, emi=(0.35, 0.25, 0.10), emi_strength=0.5)
MAT_BALLOON_COPPER = make_mat("balloon_copper", (0.85, 0.50, 0.30), metallic=0.85, roughness=0.30, emi=(0.30, 0.18, 0.12), emi_strength=0.5)
MAT_BALLOON_GOLD = make_mat("balloon_gold", (1.0, 0.85, 0.40), metallic=0.95, roughness=0.20, emi=(0.55, 0.45, 0.20), emi_strength=0.8)
MAT_BALLOON_IRON = make_mat("balloon_iron", (0.40, 0.35, 0.30), metallic=0.85, roughness=0.45)
MAT_RIVET = make_mat("rivet", (0.55, 0.40, 0.20), metallic=0.85, roughness=0.40, emi=(0.20, 0.15, 0.08), emi_strength=0.4)
MAT_WOOD = make_mat("wood", (0.45, 0.25, 0.15), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.25, 0.15, 0.08), roughness=0.85)
MAT_FLAME = make_mat("flame", (1.0, 0.65, 0.20), roughness=0.0, alpha=0.85, emi=(1.0, 0.65, 0.20), emi_strength=14.0)
MAT_FLAME_INNER = make_mat("flame_inner", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.30), emi_strength=18.0)
MAT_CANNON = make_mat("cannon", (0.25, 0.20, 0.20), metallic=0.7, roughness=0.40)
MAT_FLAG_RED = make_mat("flag_red", (0.85, 0.20, 0.15), roughness=0.7, emi=(0.35, 0.05, 0.05), emi_strength=0.4)
MAT_FLAG_BLUE = make_mat("flag_blue", (0.20, 0.40, 0.85), roughness=0.7, emi=(0.05, 0.15, 0.35), emi_strength=0.4)
MAT_FLAG_YELLOW = make_mat("flag_yellow", (0.95, 0.85, 0.25), roughness=0.7, emi=(0.45, 0.40, 0.10), emi_strength=0.4)
MAT_SPARK = make_mat("spark", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_FRAGMENT = make_mat("fragment", (0.40, 0.35, 0.30), metallic=0.6, roughness=0.55)
MAT_PLATFORM = make_mat("platform", (0.55, 0.40, 0.25), roughness=0.6, emi=(0.20, 0.15, 0.08), emi_strength=0.3)
MAT_BIRD_MECH = make_mat("bird_mech", (0.65, 0.45, 0.20), metallic=0.7, roughness=0.35, emi=(0.25, 0.18, 0.08), emi_strength=0.4)


# --- backdrop : steampunk sky ----------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 12), mat=MAT_SKY)
# sun
sun_p = empty("sun_p", (-9, 13, 10))
sun = smooth_sphere("sun", r=1.3, segs=24, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.0, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=2.8, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# 15 clouds
clouds = []
for ck in range(15):
    cx = random.uniform(-18, 18)
    cy = random.uniform(2, 12)
    cz = random.uniform(4, 14)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    for j in range(random.randint(3, 5)):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.7, 1.1), segs=14, rings=10, loc=(random.uniform(-0.9, 0.9), random.uniform(-0.2, 0.2), random.uniform(-0.6, 0.6)), parent=cp, mat=MAT_CLOUD, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.4, 0.8)


# --- 8 MONTGOLFIÈRES STEAMPUNK ----------------------------------------
BALLOON_MATS = [MAT_BALLOON_BRASS, MAT_BALLOON_COPPER, MAT_BALLOON_GOLD]
FLAG_MATS = [MAT_FLAG_RED, MAT_FLAG_BLUE, MAT_FLAG_YELLOW]
balloons = []
for bi in range(8):
    a = bi * (math.pi * 2 / 8) + random.uniform(-0.1, 0.1)
    r = random.uniform(5, 9)
    bx = math.cos(a) * r
    by = random.uniform(5, 9)
    bz = math.sin(a) * r * 0.7
    bp = empty(f"balloon_{bi}_p", (bx, by, bz))
    balloons.append({"p": bp, "phase": bi * 0.30, "base": (bx, by, bz)})
    bmat = BALLOON_MATS[bi % 3]
    # main envelope sphere (metallic) + ribbed bands
    envelope = smooth_sphere(f"balloon_{bi}_env", r=1.4, segs=24, rings=18, loc=(0, 0.5, 0), parent=bp, mat=bmat, scale=(1.0, 1.3, 1.0))
    # 4 ribbed bands (horizontal rings) — using flat cones
    for rb in range(4):
        ry_off = -0.6 + rb * 0.4
        smooth_cone(f"balloon_{bi}_rib_{rb}", r1=1.45 - abs(ry_off) * 0.2, r2=1.45 - abs(ry_off) * 0.2, depth=0.06, segs=22, loc=(0, 0.5 + ry_off, 0), parent=bp, mat=MAT_BALLOON_IRON)
    # 6 vertical ribbing seams
    for sk in range(6):
        sa = sk * (math.pi * 2 / 6)
        smooth_cone(f"balloon_{bi}_seam_{sk}", r1=0.03, r2=0.03, depth=2.7, segs=4, loc=(math.cos(sa) * 1.42, 0.5, math.sin(sa) * 1.42), parent=bp, mat=MAT_BALLOON_IRON)
    # 8 rivets around top
    for rk in range(8):
        ra = rk * (math.pi * 2 / 8)
        smooth_sphere(f"balloon_{bi}_rv_{rk}", r=0.05, segs=10, rings=6, loc=(math.cos(ra) * 0.30, 1.7, math.sin(ra) * 0.30), parent=bp, mat=MAT_RIVET)
    # 4 ropes connecting envelope to gondola
    for rk in range(4):
        ra = rk * (math.pi * 2 / 4) + math.pi / 4
        rope = smooth_cone(f"balloon_{bi}_rope_{rk}", r1=0.015, r2=0.015, depth=1.2, segs=4, loc=(math.cos(ra) * 0.6, -0.65, math.sin(ra) * 0.6), parent=bp, mat=MAT_WOOD_DARK)
    # GONDOLA (wood basket articulée)
    gondola_p = empty(f"balloon_{bi}_gondola_p", (0, -1.25, 0), parent=bp)
    beveled_cube(f"balloon_{bi}_gondola", (1.0, 0.45, 0.85), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=gondola_p, mat=MAT_WOOD)
    # gondola trim
    beveled_cube(f"balloon_{bi}_gondola_trim", (1.05, 0.06, 0.90), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.20, 0), parent=gondola_p, mat=MAT_BALLOON_COPPER)
    # 2 BRÛLEURS avec flammes
    burners = []
    for kk, kx in [(0, -0.30), (1, 0.30)]:
        burner_p = empty(f"balloon_{bi}_burner_p_{kk}", (kx, -0.50, 0), parent=bp)
        # cone burner
        smooth_cone(f"balloon_{bi}_burner_{kk}", r1=0.12, r2=0.08, depth=0.20, segs=10, loc=(0, 0.10, 0), parent=burner_p, mat=MAT_BALLOON_IRON)
        # flame
        f_out = smooth_sphere(f"balloon_{bi}_fl_{kk}", r=0.18, segs=14, rings=10, loc=(0, 0.30, 0), parent=burner_p, mat=MAT_FLAME, scale=(0.8, 1.6, 0.8))
        f_in = smooth_sphere(f"balloon_{bi}_fl_in_{kk}", r=0.10, segs=12, rings=8, loc=(0, 0.30, 0), parent=burner_p, mat=MAT_FLAME_INNER, scale=(0.6, 1.8, 0.6))
        burners.append({"out": f_out, "in": f_in, "phase": kk * 0.30 + bi * 0.10})
    balloons[bi]["burners"] = burners

    # PROPELLER back
    prop_p = empty(f"balloon_{bi}_prop_p", (-1.2, -1.25, 0), parent=bp)
    for pb in range(4):
        blade = beveled_cube(f"balloon_{bi}_prop_b_{pb}", (0.06, 0.55, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.25, 0), parent=prop_p, mat=MAT_BALLOON_COPPER)
        blade.rotation_euler = (0, math.radians(90 * pb), 0)
    # hub
    smooth_sphere(f"balloon_{bi}_prop_hub", r=0.10, segs=14, rings=10, loc=(-1.2, -1.25, 0), parent=bp, mat=MAT_BALLOON_GOLD)
    balloons[bi]["prop"] = prop_p

    # 2 CANONS latéraux
    cannons = []
    for ck, cz in [(0, 0.55), (1, -0.55)]:
        cannon_p = empty(f"balloon_{bi}_cannon_p_{ck}", (0.50, -1.25, cz), parent=bp)
        cannon_p.rotation_euler = (0, math.radians(90 if cz > 0 else -90), 0)
        smooth_cone(f"balloon_{bi}_cannon_{ck}", r1=0.10, r2=0.08, depth=0.60, segs=10, loc=(0, 0.30, 0), parent=cannon_p, mat=MAT_CANNON)
        # muzzle
        smooth_sphere(f"balloon_{bi}_cannon_muzzle_{ck}", r=0.10, segs=12, rings=8, loc=(0, 0.65, 0), parent=cannon_p, mat=MAT_BALLOON_IRON)
        cannons.append({"p": cannon_p, "phase": ck * 0.40 + bi * 0.20, "side": cz})
    balloons[bi]["cannons"] = cannons

    # DRAPEAU sur top
    flag_p = empty(f"balloon_{bi}_flag_p", (0, 2.0, 0), parent=bp)
    smooth_cone(f"balloon_{bi}_flag_pole", r1=0.025, r2=0.025, depth=0.60, segs=6, loc=(0, 0.30, 0), parent=flag_p, mat=MAT_BALLOON_IRON)
    fmat = FLAG_MATS[bi % 3]
    flag_inner = empty(f"balloon_{bi}_flag_inner", (0, 0.55, 0), parent=flag_p)
    beveled_cube(f"balloon_{bi}_flag_cloth", (0.06, 0.20, 0.35), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.20), parent=flag_inner, mat=fmat)
    balloons[bi]["flag"] = flag_inner


# --- 5 DIRIGEABLES (smaller airships) ---------------------------------
dirigibles = []
for di in range(5):
    a = di * (math.pi * 2 / 5) + 0.3
    r = random.uniform(8, 12)
    dx = math.cos(a) * r
    dy = random.uniform(7, 11)
    dz = math.sin(a) * r * 0.6
    dp = empty(f"dirig_{di}_p", (dx, dy, dz))
    dirigibles.append({"p": dp, "phase": di * 0.40, "base": (dx, dy, dz)})
    # main envelope ovoid
    smooth_sphere(f"dirig_{di}_env", r=0.85, segs=20, rings=14, loc=(0, 0, 0), parent=dp, mat=MAT_BALLOON_BRASS, scale=(2.2, 0.85, 0.85))
    # 3 trim rings
    for tb in range(3):
        tbx = -0.80 + tb * 0.80
        smooth_cone(f"dirig_{di}_ring_{tb}", r1=0.78, r2=0.78, depth=0.04, segs=18, loc=(tbx, 0, 0), parent=dp, mat=MAT_BALLOON_COPPER)
        rng = bpy.data.objects.get(f"dirig_{di}_ring_{tb}")
        if rng:
            rng.rotation_euler = (0, math.radians(90), 0)
    # gondola
    beveled_cube(f"dirig_{di}_gondola", (0.85, 0.30, 0.35), bevel_offset=0.04, bevel_segments=2, loc=(0, -0.75, 0), parent=dp, mat=MAT_WOOD)
    # propeller back
    prop_p_d = empty(f"dirig_{di}_prop_p", (-1.5, 0, 0), parent=dp)
    for pb in range(3):
        blade = beveled_cube(f"dirig_{di}_prop_b_{pb}", (0.03, 0.35, 0.03), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.15, 0), parent=prop_p_d, mat=MAT_BALLOON_COPPER)
        blade.rotation_euler = (0, math.radians(120 * pb), 0)
    dirigibles[di]["prop"] = prop_p_d


# --- VILLE VOLANTE centrale (3 tours métal + ponts) ------------------
city_p = empty("city", (0, 2, 0))
# 3 towers
for tk in range(3):
    ta = tk * (math.pi * 2 / 3)
    tx = math.cos(ta) * 2
    tz = math.sin(ta) * 2
    th = random.uniform(2.5, 3.5)
    # tower base
    smooth_cone(f"city_t{tk}_base", r1=0.55, r2=0.45, depth=th, segs=14, loc=(tx, th / 2, tz), parent=city_p, mat=MAT_BALLOON_IRON)
    # tower top dome
    smooth_sphere(f"city_t{tk}_top", r=0.50, segs=18, rings=14, loc=(tx, th + 0.30, tz), parent=city_p, mat=MAT_BALLOON_COPPER, scale=(1.0, 0.6, 1.0))
    # 4 small chimneys
    for ck in range(4):
        ca = ck * (math.pi * 2 / 4)
        smooth_cone(f"city_t{tk}_c_{ck}", r1=0.06, r2=0.05, depth=0.40, segs=8, loc=(tx + math.cos(ca) * 0.25, th + 0.55, tz + math.sin(ca) * 0.25), parent=city_p, mat=MAT_BALLOON_IRON)
# 3 ponts between towers
for bk in range(3):
    a1 = bk * (math.pi * 2 / 3)
    a2 = ((bk + 1) % 3) * (math.pi * 2 / 3)
    x1 = math.cos(a1) * 2
    z1 = math.sin(a1) * 2
    x2 = math.cos(a2) * 2
    z2 = math.sin(a2) * 2
    midx = (x1 + x2) / 2
    midz = (z1 + z2) / 2
    dx = x2 - x1
    dz = z2 - z1
    angle = math.atan2(dz, dx)
    length = math.sqrt(dx**2 + dz**2)
    bridge = beveled_cube(f"city_bridge_{bk}", (length, 0.10, 0.30), bevel_offset=0.03, bevel_segments=2, loc=(midx, 2.5, midz), parent=city_p, mat=MAT_WOOD)
    bridge.rotation_euler = (0, -angle, 0)


# --- 30 PLATES-FORMES flottantes en construction ---------------------
platforms = []
for pi in range(30):
    a = pi * (math.pi * 2 / 30) + random.uniform(-0.2, 0.2)
    r = random.uniform(7, 14)
    px = math.cos(a) * r
    py = random.uniform(3, 11)
    pz = math.sin(a) * r * 0.6
    pp = empty(f"plat_{pi}_p", (px, py, pz))
    platforms.append({"p": pp, "phase": pi * 0.10, "base": (px, py, pz)})
    # platform base
    beveled_cube(f"plat_{pi}", (random.uniform(0.6, 1.2), 0.20, random.uniform(0.6, 1.2)), bevel_offset=0.03, bevel_segments=2, loc=(0, 0, 0), parent=pp, mat=MAT_PLATFORM)
    # 4 small chains
    for ck in range(4):
        ca = ck * (math.pi * 2 / 4) + math.pi / 4
        smooth_cone(f"plat_{pi}_c_{ck}", r1=0.015, r2=0.015, depth=0.50, segs=4, loc=(math.cos(ca) * 0.35, 0.30, math.sin(ca) * 0.35), parent=pp, mat=MAT_BALLOON_IRON)


# --- 50 ÉTINCELLES parabolic ----------------------------------------
sparks = []
for sk in range(50):
    a = sk * (math.pi * 2 / 50) + random.uniform(-0.3, 0.3)
    r = random.uniform(3, 9)
    sx = math.cos(a) * r
    sy = random.uniform(3, 8)
    sz = math.sin(a) * r
    sp_obj = smooth_sphere(f"spark_{sk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(sx, sy, sz), mat=MAT_SPARK)
    sp_obj["_base"] = (sx, sy, sz)
    sp_obj["_phase"] = sk * 0.10
    sparks.append(sp_obj)


# --- 12 FRAGMENTS flottants ------------------------------------------
fragments = []
for fk in range(12):
    a = fk * (math.pi * 2 / 12) + random.uniform(-0.3, 0.3)
    r = random.uniform(4, 10)
    fx = math.cos(a) * r
    fy = random.uniform(3, 7)
    fz = math.sin(a) * r
    fr = beveled_cube(f"frag_{fk}", (random.uniform(0.15, 0.25), random.uniform(0.10, 0.15), random.uniform(0.15, 0.25)), bevel_offset=0.02, bevel_segments=2, loc=(fx, fy, fz), mat=MAT_FRAGMENT)
    fr["_base"] = (fx, fy, fz)
    fr["_phase"] = fk * 0.12
    fragments.append(fr)


# --- 8 OISEAUX MÉCANIQUES ----------------------------------------------
mech_birds = []
for bk in range(8):
    a = bk * (math.pi * 2 / 8) + 0.5
    r = random.uniform(9, 14)
    by = random.uniform(6, 10)
    bp = empty(f"mbird_{bk}_p", (math.cos(a) * r, by, math.sin(a) * r))
    smooth_sphere(f"mbird_{bk}_body", r=0.15, segs=12, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD_MECH, scale=(1.4, 0.7, 0.7))
    # 2 wings métal
    wL = empty(f"mbird_{bk}_wL", (0, 0.03, 0.06), parent=bp)
    wR = empty(f"mbird_{bk}_wR", (0, 0.03, -0.06), parent=bp)
    smooth_sphere(f"mbird_{bk}_wL_b", r=0.15, segs=12, rings=6, loc=(0, 0, 0.20), parent=wL, mat=MAT_BIRD_MECH, scale=(0.5, 0.10, 1.5))
    smooth_sphere(f"mbird_{bk}_wR_b", r=0.15, segs=12, rings=6, loc=(0, 0, -0.20), parent=wR, mat=MAT_BIRD_MECH, scale=(0.5, 0.10, 1.5))
    mech_birds.append({"p": bp, "wL": wL, "wR": wR, "a": a, "r": r, "by": by, "phase": bk * 0.30})


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

    # 8 balloons : float independently
    for bd in balloons:
        bx_, by_, bz_ = bd["base"]
        ph = bd["phase"]
        ny = by_ + 0.5 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        nx = bx_ + 0.3 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        nz = bz_ + 0.3 * math.cos(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(bd["p"], f, "location", (nx, ny, nz))
        # roll + tilt
        roll = math.radians(8 * math.sin(2 * math.pi * tt * 1.0 + ph * math.pi))
        tilt = math.radians(5 * math.cos(2 * math.pi * tt * 1.2 + ph * math.pi))
        kf(bd["p"], f, "rotation_euler", (tilt, math.radians(10 * math.sin(2 * math.pi * tt * 0.4 + ph)), roll))
        # propeller spin
        kf(bd["prop"], f, "rotation_euler", (math.radians(360 * tt * 6), 0, 0))
        # 2 burners flames pulse
        for bu in bd["burners"]:
            ph_b = bu["phase"]
            ps = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 4 + ph_b * math.pi)
            kf(bu["out"], f, "scale", (ps * 0.8, ps * 1.6, ps * 0.8))
            kf(bu["in"], f, "scale", (ps * 0.6, ps * 1.8, ps * 0.6))
        # 2 cannons recoil cyclic (slight back-forth)
        for cn in bd["cannons"]:
            ph_c = cn["phase"]
            recoil = -0.08 * abs(math.sin(2 * math.pi * tt * 1.5 + ph_c * math.pi))
            kf(cn["p"], f, "location", (0.50 + recoil, -1.25, cn["side"]))
        # flag wave
        kf(bd["flag"], f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 4)), math.radians(10 * math.cos(2 * math.pi * tt * 4.5))))

    # 5 dirigibles : drift + propeller spin
    for dd in dirigibles:
        bx_, by_, bz_ = dd["base"]
        ph = dd["phase"]
        ny = by_ + 0.4 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        nx = bx_ + 0.4 * math.cos(2 * math.pi * tt * 0.5 + ph * math.pi)
        kf(dd["p"], f, "location", (nx, ny, bz_))
        kf(dd["p"], f, "rotation_euler", (0, math.radians(15 * math.sin(2 * math.pi * tt * 0.3 + ph)), math.radians(3 * math.sin(2 * math.pi * tt * 1.2 + ph))))
        kf(dd["prop"], f, "rotation_euler", (math.radians(360 * tt * 8), 0, 0))

    # 30 platforms rotate Y subtle + bob
    for pt in platforms:
        bx_, by_, bz_ = pt["base"]
        ph = pt["phase"]
        ny = by_ + 0.20 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(pt["p"], f, "location", (bx_, ny, bz_))
        kf(pt["p"], f, "rotation_euler", (0, math.radians(60 * tt + ph * 30), 0))

    # 50 sparks parabolic
    for sp_obj in sparks:
        bx_, by_, bz_ = sp_obj["_base"]
        ph = sp_obj["_phase"]
        local = (tt * 1.5 + ph) % 1.0
        ny = by_ + 4.0 * local * (1 - local)
        nx = bx_ + 0.4 * local
        nz = bz_ + 0.4 * local
        kf(sp_obj, f, "location", (nx, ny, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 5 + ph * math.pi))
        kf(sp_obj, f, "scale", (sc, sc, sc))

    # 12 fragments drift + rotate XYZ
    for fr in fragments:
        bx_, by_, bz_ = fr["_base"]
        ph = fr["_phase"]
        ny = by_ + 0.4 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi)
        nx = bx_ + 0.3 * math.cos(2 * math.pi * tt * 0.7 + ph * math.pi)
        kf(fr, f, "location", (nx, ny, bz_))
        kf(fr, f, "rotation_euler", (math.radians(180 * tt + ph * 30), math.radians(120 * tt + ph * 40), math.radians(90 * tt + ph * 20)))

    # 8 mech birds flap + orbit
    for mb in mech_birds:
        ang = mb["a"] + tt * 2 * math.pi * 0.4
        bx_ = math.cos(ang) * mb["r"]
        bz_ = math.sin(ang) * mb["r"]
        by_ = mb["by"] + 0.3 * math.sin(2 * math.pi * tt * 1.5 + mb["phase"])
        kf(mb["p"], f, "location", (bx_, by_, bz_))
        kf(mb["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(55) * math.sin(2 * math.pi * tt * 8 + mb["phase"])
        kf(mb["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(mb["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # 15 clouds drift
    for cp in clouds:
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 5 - 2.5
        if new_x > 18:
            new_x -= 36
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))

    # sun pulse + halos breathe
    sp = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sp, sp, sp))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        br = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (br, br, br))

    # city subtle rotate
    kf(city_p, f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 0.3)), 0))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_steampunk_armada_balloons] wrote {OUT}")
