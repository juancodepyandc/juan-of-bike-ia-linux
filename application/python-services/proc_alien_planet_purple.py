"""
proc_alien_planet_purple.py — 168e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Planète alien violette mystérieuse :
- sol violet rocheux bevelé
- 8 montagnes coniques de cristal
- 12 plantes aliens bioluminescentes (tige + tête pulsante)
- 6 créatures aliens articulées (corps + 4 tentacules wave)
- 4 lunes émissives orbitant
- 30 spores volants
- 2 vaisseaux UFO explorateurs
- 6 champignons étranges
- ciel violet 2 soleils
- 50 étoiles
- gaz lumineux drift
- structure alien centrale rotative

Animations multi-axes simultanées :
- 4 lunes orbit ciel rates différents
- 12 plantes pulse + sway
- 6 créatures aliens tentacules wave
- 30 spores drift 3D
- 2 UFOs hover + spin
- structure alien rotation
- gaz lumineux drift

Sortie : output/3d/pbr_alien_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_alien_proc.glb"))

random.seed(0xA17EE9)


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
MAT_SKY = make_mat("sky_alien", (0.20, 0.10, 0.35), roughness=1.0, emi=(0.25, 0.10, 0.40), emi_strength=1.2)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=5.0)
MAT_SUN_A = make_mat("sun_A", (0.95, 0.55, 0.85), roughness=0.0, emi=(0.95, 0.55, 0.85), emi_strength=12.0)
MAT_SUN_B = make_mat("sun_B", (0.55, 0.95, 0.85), roughness=0.0, emi=(0.55, 0.95, 0.85), emi_strength=10.0)
MAT_MOON_A = make_mat("moon_A", (0.85, 0.55, 0.95), roughness=0.0, emi=(0.85, 0.55, 0.95), emi_strength=8.0)
MAT_MOON_B = make_mat("moon_B", (0.55, 0.85, 1.0), roughness=0.0, emi=(0.55, 0.85, 1.0), emi_strength=8.0)
MAT_MOON_C = make_mat("moon_C", (1.0, 0.85, 0.55), roughness=0.0, emi=(1.0, 0.85, 0.55), emi_strength=8.0)
MAT_MOON_D = make_mat("moon_D", (0.45, 0.95, 0.45), roughness=0.0, emi=(0.45, 0.95, 0.45), emi_strength=8.0)
MAT_GROUND_P = make_mat("ground_purple", (0.30, 0.15, 0.40), roughness=0.85, emi=(0.15, 0.05, 0.25), emi_strength=0.4)
MAT_GROUND_DARK = make_mat("ground_dark", (0.15, 0.08, 0.20), roughness=0.95)
MAT_CRYSTAL_MNT_A = make_mat("crystal_A", (0.65, 0.30, 0.95), roughness=0.10, emi=(0.65, 0.30, 0.95), emi_strength=6.0)
MAT_CRYSTAL_MNT_B = make_mat("crystal_B", (0.30, 0.85, 0.95), roughness=0.10, emi=(0.30, 0.85, 0.95), emi_strength=6.0)
MAT_PLANT_STEM = make_mat("plant_stem", (0.20, 0.55, 0.25), roughness=0.6, emi=(0.10, 0.30, 0.10), emi_strength=0.5)
MAT_PLANT_HEAD_A = make_mat("plant_head_A", (0.95, 0.40, 0.85), roughness=0.30, emi=(0.95, 0.40, 0.85), emi_strength=9.0)
MAT_PLANT_HEAD_B = make_mat("plant_head_B", (0.40, 0.95, 0.85), roughness=0.30, emi=(0.40, 0.95, 0.85), emi_strength=9.0)
MAT_PLANT_HEAD_C = make_mat("plant_head_C", (0.85, 0.95, 0.40), roughness=0.30, emi=(0.85, 0.95, 0.40), emi_strength=9.0)
MAT_CREATURE_BODY = make_mat("creature_body", (0.40, 0.20, 0.55), roughness=0.6, emi=(0.20, 0.10, 0.30), emi_strength=0.6)
MAT_CREATURE_EYE = make_mat("creature_eye", (1.0, 0.85, 0.30), roughness=0.0, emi=(1.0, 0.85, 0.30), emi_strength=12.0)
MAT_CREATURE_TENT = make_mat("creature_tent", (0.55, 0.30, 0.75), roughness=0.5, alpha=0.85, emi=(0.30, 0.15, 0.45), emi_strength=0.7)
MAT_SPORE_A = make_mat("spore_A", (0.85, 0.55, 1.0), roughness=0.0, emi=(0.85, 0.55, 1.0), emi_strength=8.0)
MAT_SPORE_B = make_mat("spore_B", (0.55, 0.95, 1.0), roughness=0.0, emi=(0.55, 0.95, 1.0), emi_strength=8.0)
MAT_UFO_BODY = make_mat("ufo_body", (0.85, 0.85, 0.95), metallic=0.85, roughness=0.30, emi=(0.30, 0.30, 0.40), emi_strength=0.5)
MAT_UFO_DOME = make_mat("ufo_dome", (0.55, 0.95, 1.0), roughness=0.10, alpha=0.55, emi=(0.55, 0.95, 1.0), emi_strength=5.0)
MAT_UFO_LIGHT = make_mat("ufo_light", (1.0, 0.55, 0.85), roughness=0.0, emi=(1.0, 0.55, 0.85), emi_strength=14.0)
MAT_MUSH_STEM = make_mat("mush_stem", (0.30, 0.15, 0.35), roughness=0.6)
MAT_MUSH_CAP = make_mat("mush_cap", (0.95, 0.45, 0.95), roughness=0.30, emi=(0.95, 0.45, 0.95), emi_strength=7.0)
MAT_GAS = make_mat("gas", (0.65, 0.35, 0.95), roughness=1.0, alpha=0.35, emi=(0.55, 0.25, 0.85), emi_strength=1.5)
MAT_STRUCTURE = make_mat("structure", (0.35, 0.30, 0.45), metallic=0.65, roughness=0.45, emi=(0.18, 0.15, 0.25), emi_strength=0.5)
MAT_STRUCTURE_GLOW = make_mat("structure_glow", (0.85, 0.45, 1.0), roughness=0.0, emi=(0.85, 0.45, 1.0), emi_strength=10.0)


# --- backdrop : alien sky --------------------------------------------------
sky = beveled_cube("sky_back", (50, 0.2, 28), bevel_offset=0.05, bevel_segments=2, loc=(0, 18, 12), mat=MAT_SKY)

# 50 stars
for i in range(50):
    smooth_sphere(f"star_{i}", r=random.uniform(0.07, 0.12), segs=10, rings=8, loc=(random.uniform(-22, 22), random.uniform(14, 17.5), random.uniform(8, 16)), mat=MAT_STAR)

# 2 suns
sun_A_p = empty("sun_A_p", (-10, 14, 10))
smooth_sphere("sun_A", r=1.2, segs=24, rings=18, loc=(0, 0, 0), parent=sun_A_p, mat=MAT_SUN_A)
sun_B_p = empty("sun_B_p", (12, 13, 8))
smooth_sphere("sun_B", r=0.9, segs=22, rings=16, loc=(0, 0, 0), parent=sun_B_p, mat=MAT_SUN_B)


# --- ground alien purple --------------------------------------------------
ground = beveled_cube("ground", (30, 0.2, 24), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.10, 0), mat=MAT_GROUND_P)
# dark patches
for dp in range(12):
    dx = random.uniform(-12, 12)
    dz = random.uniform(-4, 8)
    smooth_sphere(f"dark_patch_{dp}", r=random.uniform(0.8, 1.6), segs=14, rings=8, loc=(dx, 0.05, dz), mat=MAT_GROUND_DARK, scale=(1.0, 0.10, 1.0))


# --- 8 montagnes coniques de cristal ------------------------------------
mountains = []
for mk in range(8):
    a = mk * (math.pi * 2 / 8) + random.uniform(-0.1, 0.1)
    r = random.uniform(7, 11)
    mx = math.cos(a) * r
    mz = math.sin(a) * r * 0.7
    mh = random.uniform(3.5, 6.5)
    mmat = MAT_CRYSTAL_MNT_A if mk % 2 == 0 else MAT_CRYSTAL_MNT_B
    mtn = smooth_cone(f"mnt_{mk}", r1=random.uniform(0.8, 1.4), r2=0.05, depth=mh, segs=12, loc=(mx, mh / 2, mz), mat=mmat)
    # small crystal cluster at base
    for ck in range(4):
        ca = ck * (math.pi * 2 / 4)
        smooth_cone(f"mnt_{mk}_cl_{ck}", r1=0.0, r2=0.15, depth=0.40, segs=6, loc=(mx + math.cos(ca) * 1.2, 0.20, mz + math.sin(ca) * 1.2), mat=mmat)


# --- 12 plantes aliens bioluminescentes ---------------------------------
plants = []
PLANT_HEAD_MATS = [MAT_PLANT_HEAD_A, MAT_PLANT_HEAD_B, MAT_PLANT_HEAD_C]
for pk in range(12):
    a = pk * (math.pi * 2 / 12) + random.uniform(-0.2, 0.2)
    r = random.uniform(3, 7)
    px = math.cos(a) * r
    pz = math.sin(a) * r * 0.8
    pp = empty(f"plant_{pk}_p", (px, 0, pz))
    plants.append(pp)
    # stem (long curvy)
    h = random.uniform(1.5, 3.5)
    smooth_cone(f"plant_{pk}_stem", r1=0.08, r2=0.05, depth=h, segs=10, loc=(0, h / 2, 0), parent=pp, mat=MAT_PLANT_STEM)
    # head bioluminescente
    head_mat = PLANT_HEAD_MATS[pk % 3]
    smooth_sphere(f"plant_{pk}_head", r=random.uniform(0.20, 0.35), segs=18, rings=14, loc=(0, h + 0.15, 0), parent=pp, mat=head_mat)
    # 5 petals
    for pt in range(5):
        pa = pt * (math.pi * 2 / 5)
        smooth_cone(f"plant_{pk}_pet_{pt}", r1=0.08, r2=0.0, depth=0.25, segs=6, loc=(math.cos(pa) * 0.20, h + 0.05, math.sin(pa) * 0.20), parent=pp, mat=head_mat)
    pp["_phase"] = pk * 0.25


# --- 6 créatures aliens articulées ---------------------------------------
creatures = []
for ck in range(6):
    a = ck * (math.pi * 2 / 6) + 0.5
    r = random.uniform(4, 8)
    cx = math.cos(a) * r
    cz = math.sin(a) * r * 0.7
    cp = empty(f"creature_{ck}_p", (cx, 0.30, cz))
    creatures.append({"p": cp, "phase": ck * 0.5})
    # body (round)
    smooth_sphere(f"creature_{ck}_body", r=0.40, segs=20, rings=14, loc=(0, 0.20, 0), parent=cp, mat=MAT_CREATURE_BODY, scale=(1.0, 0.85, 1.0))
    # single big eye on top
    smooth_sphere(f"creature_{ck}_eye", r=0.18, segs=18, rings=12, loc=(0, 0.55, 0), parent=cp, mat=MAT_CREATURE_EYE)
    # 4 tentacules wave
    tents = []
    for tk in range(4):
        ta = tk * (math.pi * 2 / 4)
        tent_p = empty(f"creature_{ck}_tent_{tk}", (math.cos(ta) * 0.25, 0.05, math.sin(ta) * 0.25), parent=cp)
        # 3 segments
        cur = tent_p
        for sg in range(3):
            e = empty(f"creature_{ck}_tseg_p_{tk}_{sg}", (0, -0.18, 0), parent=cur)
            smooth_sphere(f"creature_{ck}_tseg_{tk}_{sg}", r=0.08 - sg * 0.015, segs=12, rings=8, loc=(0, -0.09, 0), parent=e, mat=MAT_CREATURE_TENT, scale=(1.0, 1.4, 1.0))
            cur = e
        tents.append(tent_p)
    creatures[ck]["tents"] = tents


# --- 4 lunes émissives orbitant -------------------------------------------
MOON_MATS = [MAT_MOON_A, MAT_MOON_B, MAT_MOON_C, MAT_MOON_D]
moons = []
for mk in range(4):
    ma = mk * (math.pi * 2 / 4) + 0.3
    mr = 12 + mk * 1.0
    mp = empty(f"moon_{mk}_p", (math.cos(ma) * mr, 9 + mk * 0.5, math.sin(ma) * mr))
    moons.append({"p": mp, "a": ma, "r": mr, "y": 9 + mk * 0.5, "phase": mk * 0.7})
    smooth_sphere(f"moon_{mk}", r=random.uniform(0.50, 0.85), segs=22, rings=16, loc=(0, 0, 0), parent=mp, mat=MOON_MATS[mk])


# --- 30 spores volants ---------------------------------------------------
spores = []
for sk in range(30):
    smat = MAT_SPORE_A if sk % 2 == 0 else MAT_SPORE_B
    sx = random.uniform(-10, 10)
    sy = random.uniform(2, 8)
    sz = random.uniform(-3, 7)
    sp_obj = smooth_sphere(f"spore_{sk}", r=random.uniform(0.06, 0.12), segs=8, rings=6, loc=(sx, sy, sz), mat=smat)
    sp_obj["_base"] = (sx, sy, sz)
    sp_obj["_phase"] = sk * 0.18
    spores.append(sp_obj)


# --- 2 UFOs explorateurs ----------------------------------------------
ufos = []
for ui in range(2):
    ux = -6 + ui * 12
    uy = 7
    uz = random.uniform(-1, 1)
    up = empty(f"ufo_{ui}_p", (ux, uy, uz))
    ufos.append({"p": up, "phase": ui * 1.5, "base_x": ux})
    # main disc (saucer)
    smooth_sphere(f"ufo_{ui}_disc", r=1.0, segs=22, rings=14, loc=(0, 0, 0), parent=up, mat=MAT_UFO_BODY, scale=(1.6, 0.30, 1.6))
    # dome (top)
    smooth_sphere(f"ufo_{ui}_dome", r=0.55, segs=18, rings=12, loc=(0, 0.25, 0), parent=up, mat=MAT_UFO_DOME, scale=(1.0, 0.7, 1.0))
    # bottom light
    smooth_sphere(f"ufo_{ui}_botlight", r=0.20, segs=14, rings=10, loc=(0, -0.20, 0), parent=up, mat=MAT_UFO_LIGHT)
    # 8 perimeter lights
    perim_lights = []
    for pl in range(8):
        pa = pl * (math.pi * 2 / 8)
        pll = smooth_sphere(f"ufo_{ui}_pl_{pl}", r=0.07, segs=10, rings=6, loc=(math.cos(pa) * 1.5, 0, math.sin(pa) * 1.5), parent=up, mat=MAT_UFO_LIGHT)
        perim_lights.append(pll)
    ufos[ui]["perim"] = perim_lights


# --- 6 champignons étranges ---------------------------------------------
mushrooms = []
for mk in range(6):
    mx = random.uniform(-9, 9)
    mz = random.uniform(-3, 7)
    if abs(mx) < 2 and abs(mz) < 2:
        continue
    mp = empty(f"mush_{mk}", (mx, 0, mz))
    mushrooms.append(mp)
    h = random.uniform(0.6, 1.2)
    smooth_cone(f"mush_{mk}_stem", r1=0.12, r2=0.10, depth=h, segs=10, loc=(0, h / 2, 0), parent=mp, mat=MAT_MUSH_STEM)
    smooth_sphere(f"mush_{mk}_cap", r=0.40, segs=18, rings=12, loc=(0, h + 0.10, 0), parent=mp, mat=MAT_MUSH_CAP, scale=(1.0, 0.55, 1.0))
    # tiny dots on cap
    for dk in range(4):
        da = dk * (math.pi * 2 / 4)
        smooth_sphere(f"mush_{mk}_dot_{dk}", r=0.05, segs=8, rings=6, loc=(math.cos(da) * 0.25, h + 0.20, math.sin(da) * 0.25), parent=mp, mat=MAT_GROUND_DARK)
    mp["_phase"] = mk * 0.30


# --- gaz lumineux drift ------------------------------------------------
gas_puffs = []
for gk in range(8):
    gx = random.uniform(-12, 12)
    gz = random.uniform(-4, 8)
    gy = random.uniform(0.5, 3)
    gp = smooth_sphere(f"gas_{gk}", r=random.uniform(1.0, 1.8), segs=14, rings=8, loc=(gx, gy, gz), mat=MAT_GAS, scale=(1.0, 0.30, 1.0))
    gp["_base"] = (gx, gy, gz)
    gp["_phase"] = gk * 0.40
    gas_puffs.append(gp)


# --- structure alien centrale rotative -----------------------------------
struct_p = empty("structure_p", (0, 0, 0))
# base
smooth_cone("struct_base", r1=1.5, r2=1.2, depth=0.50, segs=18, loc=(0, 0.25, 0), parent=struct_p, mat=MAT_STRUCTURE)
# column
smooth_cone("struct_col", r1=0.30, r2=0.25, depth=2.5, segs=14, loc=(0, 1.75, 0), parent=struct_p, mat=MAT_STRUCTURE)
# 4 rings around column
for rk in range(4):
    ry = 1.0 + rk * 0.50
    ring = smooth_cone(f"struct_ring_{rk}", r1=0.65 - rk * 0.05, r2=0.65 - rk * 0.05, depth=0.10, segs=22, loc=(0, ry, 0), parent=struct_p, mat=MAT_STRUCTURE_GLOW)
# top orb glow
smooth_sphere("struct_orb", r=0.45, segs=22, rings=16, loc=(0, 3.25, 0), parent=struct_p, mat=MAT_STRUCTURE_GLOW)
# 6 antennae radiating
for ak in range(6):
    aa = ak * (math.pi * 2 / 6)
    antenna = smooth_cone(f"struct_ant_{ak}", r1=0.05, r2=0.0, depth=0.80, segs=6, loc=(math.cos(aa) * 0.30, 3.40, math.sin(aa) * 0.30), parent=struct_p, mat=MAT_STRUCTURE)
    antenna.rotation_euler = (math.radians(45 * math.cos(aa)), 0, math.radians(45 * math.sin(aa)))


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

    # 4 moons orbit
    for mn in moons:
        ang = mn["a"] + tt * 2 * math.pi * 0.3 * (1 if mn["phase"] > 0.5 else -1)
        mx = math.cos(ang) * mn["r"]
        mz = math.sin(ang) * mn["r"]
        my = mn["y"] + 0.5 * math.sin(2 * math.pi * tt * 1.0 + mn["phase"])
        kf(mn["p"], f, "location", (mx, my, mz))

    # 12 plants pulse + sway
    for pi, pp in enumerate(plants):
        ph = pp["_phase"]
        ps = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3 + ph * math.pi)
        kf(pp, f, "scale", (ps, ps, ps))
        sway = math.radians(8) * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        kf(pp, f, "rotation_euler", (sway, 0, math.radians(5 * math.cos(2 * math.pi * tt * 1.8 + ph * math.pi))))

    # 6 creatures tentacles wave
    for cd in creatures:
        ph = cd["phase"]
        for ti, tent in enumerate(cd["tents"]):
            wave = math.radians(20 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi + ti * 0.8))
            kf(tent, f, "rotation_euler", (wave, 0, math.radians(10 * math.cos(2 * math.pi * tt * 2.2 + ph * math.pi + ti * 0.5))))
        # body bob
        bob = 0.30 + 0.10 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        cx_ = cd["p"].location.x if f > 1 else cd["p"].location.x
        cz_ = cd["p"].location.z if f > 1 else cd["p"].location.z
        kf(cd["p"], f, "location", (cx_, bob, cz_))

    # 30 spores drift 3D
    for sp in spores:
        bxp, byp, bzp = sp["_base"]
        ph = sp["_phase"]
        nx = bxp + 0.8 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        ny = byp + 0.6 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi)
        nz = bzp + 0.7 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(sp, f, "location", (nx, ny, nz))
        sc = 0.7 + 0.5 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(sp, f, "scale", (sc, sc, sc))

    # 2 UFOs hover + spin + perim lights pulse
    for uf in ufos:
        ph = uf["phase"]
        ux_ = uf["base_x"] + 0.3 * math.sin(2 * math.pi * tt * 0.5 + ph)
        uy_ = 7 + 0.5 * math.cos(2 * math.pi * tt * 0.7 + ph)
        uz_ = 0.4 * math.sin(2 * math.pi * tt * 0.6 + ph)
        kf(uf["p"], f, "location", (ux_, uy_, uz_))
        # spin
        kf(uf["p"], f, "rotation_euler", (math.radians(3 * math.sin(2 * math.pi * tt * 2)), math.radians(180 * tt + ph * 60), math.radians(2 * math.cos(2 * math.pi * tt * 2))))
        # perim lights pulse different
        for pli, pll in enumerate(uf["perim"]):
            pls = 1.0 + 0.30 * math.sin(2 * math.pi * tt * 5 + pli * (math.pi / 4))
            kf(pll, f, "scale", (pls, pls, pls))

    # 6 mushrooms pulse
    for mp_obj in mushrooms:
        ph = mp_obj["_phase"]
        ms = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 2.5 + ph * math.pi)
        kf(mp_obj, f, "scale", (ms, ms, ms))

    # 8 gas puffs drift
    for gp in gas_puffs:
        bx_, by_, bz_ = gp["_base"]
        ph = gp["_phase"]
        nx = bx_ + 1.2 * math.sin(2 * math.pi * tt * 0.4 + ph * math.pi)
        ny = by_ + 0.4 * math.cos(2 * math.pi * tt * 0.5 + ph * math.pi)
        nz = bz_ + 0.6 * math.sin(2 * math.pi * tt * 0.3 + ph * math.pi)
        kf(gp, f, "location", (nx, ny, nz))
        sc = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)
        kf(gp, f, "scale", (sc, 0.30, sc))

    # structure rotation
    kf(struct_p, f, "rotation_euler", (0, math.radians(60 * tt * 360 / 360), 0))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_alien_planet_purple] wrote {OUT}")
