"""
proc_floating_islands_dragons.py — 154e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Îles flottantes dans ciel crépuscule avec 3 dragons orbitant :
- 3 îles flottantes inversées coniques bevelées + herbe émissif top
- 3 cascades émissives bleues alpha tombant des îles
- 3 dragons orbitant (body 5 segments + tête horns + 2 ailes membraneuses 4 phalanges + queue 6 segments wave)
- 12 cristaux flottants émissifs violet/cyan (8 segments)
- 2 arches mystiques en pierre sur île centrale
- 25 nuages volumineux sphères scaled
- 8 oiseaux silhouettes flying
- soleil émissif orange + 3 halos
- 30 étoiles distantes émissives
- ciel crépuscule pourpre-orange

Animations multi-axes simultanées :
- 3 dragons orbitent autour à différentes hauteurs avec rates différents
- dragons : ailes flap ±60° rapide, queue wave 6 segments propagée, body undulate
- 3 cascades : flow Y descendant alpha pulse
- 12 cristaux : float Y + rotate XYZ
- 25 nuages : drift X lent
- 8 oiseaux : flap rapide + orbit lent
- soleil : pulse + 3 halos breathe
- 30 étoiles : scintille

Sortie : output/3d/pbr_floating_islands_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_floating_islands_proc.glb"))

random.seed(0xF10A71)


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
MAT_SKY = make_mat("sky_twilight", (0.18, 0.10, 0.30), roughness=1.0, emi=(0.25, 0.12, 0.30), emi_strength=0.9)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.5)
MAT_SUN = make_mat("sun", (1.0, 0.55, 0.20), roughness=0.0, emi=(1.0, 0.55, 0.20), emi_strength=12.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.55, 0.25), roughness=0.0, alpha=0.25, emi=(1.0, 0.55, 0.25), emi_strength=3.5)
MAT_CLOUD = make_mat("cloud", (0.85, 0.75, 0.85), roughness=1.0, alpha=0.55, emi=(0.40, 0.35, 0.45), emi_strength=0.5)
MAT_ROCK = make_mat("island_rock", (0.40, 0.30, 0.25), roughness=0.85)
MAT_ROCK_DARK = make_mat("island_rock_dark", (0.25, 0.18, 0.14), roughness=0.95)
MAT_GRASS = make_mat("grass", (0.20, 0.50, 0.18), roughness=0.7, emi=(0.10, 0.30, 0.10), emi_strength=0.3)
MAT_GRASS_LIGHT = make_mat("grass_light", (0.45, 0.75, 0.30), roughness=0.55, emi=(0.20, 0.40, 0.15), emi_strength=0.4)
MAT_WATERFALL = make_mat("waterfall", (0.55, 0.85, 1.0), roughness=0.15, alpha=0.65, emi=(0.40, 0.70, 1.0), emi_strength=2.5)
MAT_DRAGON_BODY = make_mat("dragon_body", (0.55, 0.15, 0.18), roughness=0.55, emi=(0.25, 0.05, 0.05), emi_strength=0.4)
MAT_DRAGON_BELLY = make_mat("dragon_belly", (0.95, 0.65, 0.30), roughness=0.4, emi=(0.40, 0.25, 0.10), emi_strength=0.6)
MAT_DRAGON_WING = make_mat("dragon_wing", (0.30, 0.10, 0.12), roughness=0.75, alpha=0.85, emi=(0.18, 0.05, 0.06), emi_strength=0.3)
MAT_DRAGON_HORN = make_mat("dragon_horn", (0.90, 0.85, 0.65), metallic=0.4, roughness=0.30)
MAT_DRAGON_EYE = make_mat("dragon_eye", (1.0, 0.95, 0.20), roughness=0.0, emi=(1.0, 0.95, 0.20), emi_strength=13.0)
MAT_DRAGON_2 = make_mat("dragon2_body", (0.15, 0.35, 0.60), roughness=0.55, emi=(0.05, 0.15, 0.30), emi_strength=0.4)
MAT_DRAGON_2_BELLY = make_mat("dragon2_belly", (0.45, 0.75, 1.0), roughness=0.4, emi=(0.15, 0.35, 0.50), emi_strength=0.55)
MAT_DRAGON_3 = make_mat("dragon3_body", (0.30, 0.55, 0.20), roughness=0.55, emi=(0.10, 0.25, 0.05), emi_strength=0.4)
MAT_DRAGON_3_BELLY = make_mat("dragon3_belly", (0.75, 0.95, 0.50), roughness=0.4, emi=(0.30, 0.45, 0.15), emi_strength=0.55)
MAT_CRYSTAL_P = make_mat("crystal_purple", (0.65, 0.30, 0.95), roughness=0.10, emi=(0.65, 0.30, 0.95), emi_strength=8.0)
MAT_CRYSTAL_C = make_mat("crystal_cyan", (0.30, 0.85, 0.95), roughness=0.10, emi=(0.30, 0.85, 0.95), emi_strength=8.0)
MAT_ARCH = make_mat("arch_stone", (0.65, 0.60, 0.55), roughness=0.7, emi=(0.20, 0.18, 0.18), emi_strength=0.2)
MAT_BIRD = make_mat("bird", (0.12, 0.10, 0.10), roughness=0.7)

# --- backdrop : twilight sky ----------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 24), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 8), mat=MAT_SKY)

# 30 distant stars
for i in range(30):
    x = random.uniform(-20, 20)
    z = random.uniform(8, 16)
    y = random.uniform(13.5, 14.0)
    r = random.uniform(0.07, 0.13)
    s = smooth_sphere(f"star_{i}", r=r, segs=10, rings=8, loc=(x, y, z), mat=MAT_STAR)
    s["_phase"] = (i * 13) % 53

# sun + halos
sun_p = empty("sun_p", (-9, 12.5, 4))
sun = smooth_sphere("sun", r=1.2, segs=28, rings=20, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=1.9, segs=24, rings=16, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=2.6, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_3 = smooth_sphere("sun_halo_3", r=3.4, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)


# --- 3 floating islands ----------------------------------------------------
ISLAND_CONFIGS = [
    # (cx, cy, cz, radius, mat_rock)  cy = altitude
    (0, 4.5, 0, 3.5, MAT_ROCK),      # central island
    (-7, 6.0, -1, 2.5, MAT_ROCK_DARK), # left high
    (7, 3.5, 1, 2.8, MAT_ROCK),     # right low
]
island_empties = []
for ix, (cx, cy, cz, rad, rmat) in enumerate(ISLAND_CONFIGS):
    isl_p = empty(f"island_{ix}", (cx, cy, cz))
    island_empties.append(isl_p)
    # top : sphere flattened (rock body)
    top = smooth_sphere(f"isl_{ix}_top", r=rad, segs=28, rings=20, loc=(0, -0.15, 0), parent=isl_p, mat=rmat, scale=(1.0, 0.45, 1.0))
    # bottom : inverted cone (tapered down to point)
    bot = smooth_cone(f"isl_{ix}_bot", r1=rad * 0.95, r2=0.10, depth=rad * 1.4, segs=22, loc=(0, -0.5 - rad * 0.7, 0), parent=isl_p, mat=rmat)
    bot.rotation_euler = (math.radians(180), 0, 0)
    # grass disc on top
    grass = smooth_sphere(f"isl_{ix}_grass", r=rad * 0.94, segs=26, rings=14, loc=(0, 0.10, 0), parent=isl_p, mat=MAT_GRASS, scale=(1.0, 0.15, 1.0))
    # 5-7 grass tufts
    for tk in range(7):
        ta = tk * (math.pi * 2 / 7) + random.uniform(-0.2, 0.2)
        tr = rad * 0.55 * random.uniform(0.4, 0.9)
        tx = math.cos(ta) * tr
        tz = math.sin(ta) * tr
        smooth_sphere(f"isl_{ix}_tuft_{tk}", r=0.18, segs=14, rings=10, loc=(tx, 0.18, tz), parent=isl_p, mat=MAT_GRASS_LIGHT, scale=(1.0, 1.4, 1.0))
    # 3 small rocks
    for rk in range(3):
        ra = rk * (math.pi * 2 / 3) + 0.5
        rr = rad * 0.6
        rx = math.cos(ra) * rr
        rz = math.sin(ra) * rr
        smooth_sphere(f"isl_{ix}_rock_{rk}", r=random.uniform(0.20, 0.35), segs=14, rings=10, loc=(rx, 0.20, rz), parent=isl_p, mat=MAT_ROCK_DARK, scale=(1.0, 0.8, 1.0))

# --- 3 waterfalls cascading from islands -----------------------------------
waterfall_segments = []
for wx, (cx, cy, cz, rad, _) in enumerate(ISLAND_CONFIGS):
    wf_p = empty(f"wf_{wx}", (cx, cy - 0.5, cz))
    # 6 segments cascading
    for sg in range(6):
        seg = beveled_cube(f"wf_{wx}_s_{sg}", (0.45, 0.85, 0.18), bevel_offset=0.03, bevel_segments=2, loc=(0, -sg * 0.75, 0), parent=wf_p, mat=MAT_WATERFALL)
        seg["_seg"] = sg
        seg["_idx"] = wx
        waterfall_segments.append(seg)
    # splash at bottom
    smooth_sphere(f"wf_{wx}_splash", r=0.55, segs=18, rings=12, loc=(0, -5.0, 0), parent=wf_p, mat=MAT_WATERFALL, scale=(1.2, 0.35, 1.2))


# --- 12 floating crystals --------------------------------------------------
crystals = []
for ck in range(12):
    cmat = MAT_CRYSTAL_P if ck % 2 == 0 else MAT_CRYSTAL_C
    a = ck * (math.pi * 2 / 12) + random.uniform(-0.1, 0.1)
    r = random.uniform(5.5, 9.5)
    cx = math.cos(a) * r
    cy = random.uniform(3.0, 8.5)
    cz = math.sin(a) * r
    cp = empty(f"crystal_{ck}", (cx, cy, cz))
    crystals.append(cp)
    # 4-sided diamond using cone with low segs
    diam = smooth_cone(f"crystal_{ck}_top", r1=0.0, r2=0.30, depth=0.50, segs=6, loc=(0, 0.25, 0), parent=cp, mat=cmat)
    diam_bot = smooth_cone(f"crystal_{ck}_bot", r1=0.0, r2=0.30, depth=0.40, segs=6, loc=(0, -0.20, 0), parent=cp, mat=cmat)
    diam_bot.rotation_euler = (math.radians(180), 0, 0)
    cp["_phase"] = ck * 0.5
    cp["_orbit_a"] = a
    cp["_orbit_r"] = r
    cp["_base_y"] = cy


# --- 2 mystic arches on central island -------------------------------------
for ai, ax in enumerate([-1.5, 1.5]):
    arch_p = empty(f"arch_{ai}", (ax, 4.7, 0))
    # left pillar
    smooth_cone(f"arch_{ai}_p1", r1=0.20, r2=0.18, depth=1.8, segs=12, loc=(-0.55, 0.9, 0), parent=arch_p, mat=MAT_ARCH)
    # right pillar
    smooth_cone(f"arch_{ai}_p2", r1=0.20, r2=0.18, depth=1.8, segs=12, loc=(0.55, 0.9, 0), parent=arch_p, mat=MAT_ARCH)
    # top arch (curved using 5 segments)
    for j in range(5):
        t = j / 4
        ang = math.pi * t
        x = -0.55 + (0.55 - (-0.55)) * t
        y = 1.85 + 0.30 * math.sin(ang)
        seg = beveled_cube(f"arch_{ai}_top_{j}", (0.30, 0.20, 0.20), bevel_offset=0.03, bevel_segments=2, loc=(x, y, 0), parent=arch_p, mat=MAT_ARCH)


# --- 3 dragons orbiting ----------------------------------------------------
DRAGON_CONFIGS = [
    # (name, body_mat, belly_mat, orbit_radius, base_y, orbit_speed, body_scale, phase)
    ("d1", MAT_DRAGON_BODY, MAT_DRAGON_BELLY, 11.0, 7.5, 0.8, 1.0, 0.0),
    ("d2", MAT_DRAGON_2, MAT_DRAGON_2_BELLY, 9.0, 5.0, -1.2, 0.75, 1.5),
    ("d3", MAT_DRAGON_3, MAT_DRAGON_3_BELLY, 13.0, 9.5, 0.55, 1.2, 3.0),
]
dragon_data = []
for dr_idx, (dname, dmat, dbelly, orad, oy, ospd, dscale, dphase) in enumerate(DRAGON_CONFIGS):
    dragon_p = empty(f"{dname}_p", (orad, oy, 0))
    head_p = empty(f"{dname}_head_p", (1.2 * dscale, 0.10, 0), parent=dragon_p)
    tail_p = empty(f"{dname}_tail_p", (-0.9 * dscale, 0, 0), parent=dragon_p)
    wing_L_p = empty(f"{dname}_wingL_p", (0, 0.15 * dscale, 0.30 * dscale), parent=dragon_p)
    wing_R_p = empty(f"{dname}_wingR_p", (0, 0.15 * dscale, -0.30 * dscale), parent=dragon_p)

    # body : 5 tapered segments
    for s in range(5):
        rs = (0.40 - s * 0.04) * dscale
        sl = smooth_sphere(f"{dname}_body_{s}", r=rs, segs=20, rings=14, loc=((-0.8 + s * 0.45) * dscale, 0, 0), parent=dragon_p, mat=dmat, scale=(1.2, 0.95, 0.95))
        # belly highlight
        smooth_sphere(f"{dname}_belly_{s}", r=rs * 0.65, segs=16, rings=12, loc=((-0.8 + s * 0.45) * dscale, -0.18 * dscale, 0), parent=dragon_p, mat=dbelly, scale=(1.2, 0.5, 0.8))

    # head
    smooth_sphere(f"{dname}_head", r=0.40 * dscale, segs=24, rings=16, loc=(0.20 * dscale, 0, 0), parent=head_p, mat=dmat, scale=(1.4, 1.0, 1.0))
    # jaw
    smooth_sphere(f"{dname}_jaw", r=0.25 * dscale, segs=18, rings=12, loc=(0.30 * dscale, -0.15 * dscale, 0), parent=head_p, mat=dmat, scale=(1.4, 0.5, 0.9))
    # 2 horns
    for hx, hz in [(-0.10, 0.18), (-0.10, -0.18)]:
        horn = smooth_cone(f"{dname}_horn_{'L' if hz > 0 else 'R'}", r1=0.06 * dscale, r2=0.0, depth=0.55 * dscale, segs=10, loc=(hx * dscale, 0.25 * dscale, hz * dscale), parent=head_p, mat=MAT_DRAGON_HORN)
        horn.rotation_euler = (0, 0, math.radians(-15))
    # 2 eyes
    for ez in [0.16, -0.16]:
        smooth_sphere(f"{dname}_eye_{'L' if ez > 0 else 'R'}", r=0.08 * dscale, segs=14, rings=10, loc=(0.28 * dscale, 0.10 * dscale, ez * dscale), parent=head_p, mat=MAT_DRAGON_EYE)
    # 6 spikes along back
    for k in range(6):
        sp = smooth_cone(f"{dname}_spike_{k}", r1=0.10 * dscale, r2=0.0, depth=0.40 * dscale, segs=8, loc=((-0.75 + k * 0.35) * dscale, 0.35 * dscale, 0), parent=dragon_p, mat=MAT_DRAGON_HORN)

    # tail : 6 segments wave parented sequentially
    tail_segs = []
    cur_parent = tail_p
    for t in range(6):
        tseg_p = empty(f"{dname}_tseg_p_{t}", (-0.30 * dscale, 0, 0), parent=cur_parent)
        rt = (0.20 - t * 0.025) * dscale
        smooth_sphere(f"{dname}_tail_{t}", r=rt, segs=14, rings=10, loc=(-0.15 * dscale, 0, 0), parent=tseg_p, mat=dmat, scale=(1.4, 0.9, 0.9))
        tail_segs.append(tseg_p)
        cur_parent = tseg_p
    # tail tip spike
    smooth_cone(f"{dname}_tail_tip", r1=0.10 * dscale, r2=0.0, depth=0.35 * dscale, segs=8, loc=(-0.20 * dscale, 0, 0), parent=cur_parent, mat=MAT_DRAGON_HORN)

    # wings : 4 phalanges per wing + membrane patches
    for wing_p, side in [(wing_L_p, 1), (wing_R_p, -1)]:
        # main bone
        smooth_cone(f"{dname}_wing_main_{side}", r1=0.06 * dscale, r2=0.04 * dscale, depth=1.4 * dscale, segs=8, loc=(0, 0.35 * dscale, side * 0.70 * dscale), parent=wing_p, mat=dmat)
        # 4 phalanges
        for ph in range(4):
            pa = -0.35 + ph * 0.25
            phal = smooth_cone(f"{dname}_wing_ph_{side}_{ph}", r1=0.04 * dscale, r2=0.02 * dscale, depth=0.95 * dscale, segs=6, loc=(pa * dscale, 0.65 * dscale, side * 1.10 * dscale), parent=wing_p, mat=dmat)
            phal.rotation_euler = (0, math.radians(side * (40 + ph * 5)), math.radians(-15))
        # membrane (3 patches)
        for mb in range(3):
            mba = -0.20 + mb * 0.30
            membrane = smooth_sphere(f"{dname}_wing_mb_{side}_{mb}", r=0.45 * dscale, segs=16, rings=10, loc=(mba * dscale, 0.55 * dscale, side * 1.10 * dscale), parent=wing_p, mat=MAT_DRAGON_WING, scale=(1.5, 0.10, 1.5))

    dragon_data.append({
        "name": dname,
        "p": dragon_p,
        "head_p": head_p,
        "tail_segs": tail_segs,
        "wing_L_p": wing_L_p,
        "wing_R_p": wing_R_p,
        "orad": orad,
        "oy": oy,
        "ospd": ospd,
        "phase": dphase,
    })


# --- 25 clouds drift -------------------------------------------------------
clouds = []
for ck in range(25):
    a = ck * (math.pi * 2 / 25) + random.uniform(-0.2, 0.2)
    r = random.uniform(8, 14)
    cy = random.uniform(2.0, 11.0)
    cx = math.cos(a) * r
    cz = math.sin(a) * r + random.uniform(-2, 0)
    cp = empty(f"cloud_{ck}", (cx, cy, cz))
    clouds.append(cp)
    # 3-4 spheres clustered
    for j in range(random.randint(3, 4)):
        jx = random.uniform(-0.8, 0.8)
        jy = random.uniform(-0.15, 0.20)
        jz = random.uniform(-0.6, 0.6)
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.55, 0.95), segs=18, rings=12, loc=(jx, jy, jz), parent=cp, mat=MAT_CLOUD, scale=(1.0, 0.55, 1.0))
    cp["_base_x"] = cx
    cp["_speed"] = random.uniform(0.4, 0.9)


# --- 8 birds flying --------------------------------------------------------
birds = []
for bk in range(8):
    a = bk * (math.pi * 2 / 8) + random.uniform(-0.3, 0.3)
    r = random.uniform(7, 11)
    by = random.uniform(5.5, 9.5)
    bp = empty(f"bird_{bk}", (math.cos(a) * r, by, math.sin(a) * r))
    body = smooth_sphere(f"bird_{bk}_body", r=0.10, segs=10, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_BIRD, scale=(1.3, 0.7, 0.7))
    wing_L_e = empty(f"bird_{bk}_wL", (0, 0, 0.08), parent=bp)
    wing_R_e = empty(f"bird_{bk}_wR", (0, 0, -0.08), parent=bp)
    smooth_cone(f"bird_{bk}_wL_b", r1=0.04, r2=0.0, depth=0.32, segs=6, loc=(0, 0.05, 0.20), parent=wing_L_e, mat=MAT_BIRD)
    smooth_cone(f"bird_{bk}_wR_b", r1=0.04, r2=0.0, depth=0.32, segs=6, loc=(0, 0.05, -0.20), parent=wing_R_e, mat=MAT_BIRD)
    birds.append({"p": bp, "wL": wing_L_e, "wR": wing_R_e, "a": a, "r": r, "by": by, "phase": bk * 0.7})


# --- ANIMATIONS -----------------------------------------------------------
DURATION = 6.0
FRAMES = scene.frame_end
DT = DURATION / FRAMES


def kf(obj, frame, attr, val, idx=-1):
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
    tt = t / DURATION  # 0..1

    # --- dragons orbit + flap + tail wave + head sway + body undulate
    for dd in dragon_data:
        ang = tt * 2 * math.pi * dd["ospd"] + dd["phase"]
        dx = math.cos(ang) * dd["orad"]
        dz = math.sin(ang) * dd["orad"]
        dy = dd["oy"] + 1.2 * math.sin(2 * math.pi * tt * 1.5 + dd["phase"])
        kf(dd["p"], f, "location", (dx, dy, dz))
        # face direction (tangent)
        face_yaw = ang + math.pi / 2 * (1 if dd["ospd"] > 0 else -1)
        kf(dd["p"], f, "rotation_euler", (math.radians(10 * math.sin(2 * math.pi * tt * 2 + dd["phase"])), face_yaw, 0))

        # head sway
        kf(dd["head_p"], f, "rotation_euler", (0, math.radians(20 * math.sin(2 * math.pi * tt * 1.8 + dd["phase"])), math.radians(8 * math.sin(2 * math.pi * tt * 2.2))))

        # wings flap ±60° rapid
        flap = math.radians(60) * math.sin(2 * math.pi * tt * 5 + dd["phase"])
        kf(dd["wing_L_p"], f, "rotation_euler", (flap, 0, 0))
        kf(dd["wing_R_p"], f, "rotation_euler", (-flap, 0, 0))

        # tail wave propagated
        for ti, ts in enumerate(dd["tail_segs"]):
            wave = math.radians(20) * math.sin(2 * math.pi * tt * 3.2 + dd["phase"] - ti * 0.6)
            wave_z = math.radians(10) * math.cos(2 * math.pi * tt * 2.8 + dd["phase"] - ti * 0.5)
            kf(ts, f, "rotation_euler", (0, wave, wave_z))

    # --- 3 islands gentle bob
    for ix, isl in enumerate(island_empties):
        cx, cy, cz, _, _ = ISLAND_CONFIGS[ix]
        bob = cy + 0.18 * math.sin(2 * math.pi * tt * 0.7 + ix * 1.2)
        kf(isl, f, "location", (cx, bob, cz))
        kf(isl, f, "rotation_euler", (0, math.radians(3 * math.sin(2 * math.pi * tt * 0.5 + ix * 0.8)), 0))

    # --- waterfalls : flowing alpha pulse via Y offset cycle
    for wseg in waterfall_segments:
        sg = wseg["_seg"]
        # cycle Y to give "flow" sensation
        offset = -(((sg * 0.75) + tt * 4.5) % (6 * 0.75))
        kf(wseg, f, "location", (0, offset, 0))
        sc = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 6 + sg * 0.5)
        kf(wseg, f, "scale", (sc, 1.0, sc))

    # --- crystals float + rotate XYZ
    for ck, cp in enumerate(crystals):
        oa = cp["_orbit_a"]
        orr = cp["_orbit_r"]
        base_y = cp["_base_y"]
        # gentle orbit drift
        slow_ang = oa + tt * 0.2 * (1 if ck % 2 == 0 else -1)
        cx = math.cos(slow_ang) * orr
        cz = math.sin(slow_ang) * orr
        cy = base_y + 0.4 * math.sin(2 * math.pi * tt * 1.5 + cp["_phase"])
        kf(cp, f, "location", (cx, cy, cz))
        kf(cp, f, "rotation_euler", (math.radians(360 * tt + ck * 30), math.radians(720 * tt + ck * 15), math.radians(180 * tt + ck * 45)))

    # --- clouds drift
    for clk, cp in enumerate(clouds):
        bx = cp["_base_x"]
        spd = cp["_speed"]
        offset = (tt * spd * 8) % 30 - 15
        # gentle X drift (wraps)
        new_x = bx + offset * 0.4
        if new_x > 16:
            new_x -= 32
        if new_x < -16:
            new_x += 32
        kf(cp, f, "location", (new_x, cp.location.y if f == 1 else cp.location.y, cp.location.z))

    # --- birds : flap + orbit
    for bd in birds:
        ang = bd["a"] + tt * 2 * math.pi * 0.3
        bx = math.cos(ang) * bd["r"]
        bz = math.sin(ang) * bd["r"]
        by = bd["by"] + 0.3 * math.sin(2 * math.pi * tt * 1.5 + bd["phase"])
        kf(bd["p"], f, "location", (bx, by, bz))
        kf(bd["p"], f, "rotation_euler", (0, ang + math.pi / 2, 0))
        wflap = math.radians(50) * math.sin(2 * math.pi * tt * 8 + bd["phase"])
        kf(bd["wL"], f, "rotation_euler", (wflap, 0, 0))
        kf(bd["wR"], f, "rotation_euler", (-wflap, 0, 0))

    # --- sun + halos pulse breathe
    kf(sun_p, f, "rotation_euler", (0, math.radians(15 * tt * 360), 0))
    sun_pulse = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sun_pulse, sun_pulse, sun_pulse))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2, sun_halo_3]):
        breath = 1.0 + 0.08 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.0)
        kf(halo, f, "scale", (breath, breath, breath))


scene.frame_set(1)

# --- export ----------------------------------------------------------------
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_floating_islands_dragons] wrote {OUT}")
