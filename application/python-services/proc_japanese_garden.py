"""
proc_japanese_garden.py — 117e procédural AuroraIA, Phase F++++.

Jardin zen japonais : pagode 5 étages avec toits courbés + pont rouge
arqué enjambant ruisseau + cerisier sakura en fleurs + 40 pétales
tombant en spirale + lanterne tōrō en pierre + jardin gravier ratissé
+ 3 roches zen + 5 bambous + 4 carpes koï dans bassin + chemin pas
japonais + ciel matin doux.

Animation :
- 40 pétales : chute en spirale (descend Y + rotation X)
- 4 koïs : nagent ondulation S
- 5 bambous : sway tilt
- pont : pas anim
- pétales sakura : pulse subtle scale
- ruisseau : ondulations métalliques

Sortie : output/3d/pbr_jpgarden_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_jpgarden_proc.glb"))

random.seed(0xCAFEEE)

# --- helpers ----------------------------------------------------------------

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


def cube(name, size=1.0, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def sphere(name, r=1.0, segs=24, rings=12, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, segments=segs, radius1=r1, radius2=r2, depth=depth, cap_ends=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY_MORN = make_mat("sky_morning", (0.85, 0.90, 0.95), roughness=1.0,
                          emi=(0.7, 0.78, 0.88), emi_strength=0.5)
MAT_GRAVEL = make_mat("gravel", (0.88, 0.85, 0.78), roughness=0.95)
MAT_GRASS = make_mat("grass", (0.35, 0.55, 0.25), roughness=0.85)
MAT_ROCK_ZEN = make_mat("rock_zen", (0.40, 0.38, 0.35), roughness=0.95)
MAT_PAGODA_WOOD = make_mat("pagoda_wood", (0.55, 0.20, 0.15), roughness=0.7)
MAT_PAGODA_ROOF = make_mat("pagoda_roof", (0.25, 0.10, 0.08), roughness=0.65)
MAT_PAGODA_BEAM = make_mat("pagoda_beam", (0.85, 0.70, 0.45), roughness=0.7)
MAT_PAGODA_TOP = make_mat("pagoda_top", (0.85, 0.65, 0.20), metallic=0.7, roughness=0.3,
                            emi=(0.4, 0.3, 0.05), emi_strength=0.4)
MAT_BRIDGE_RED = make_mat("bridge_red", (0.85, 0.15, 0.10), roughness=0.55,
                            emi=(0.35, 0.05, 0.02), emi_strength=0.3)
MAT_BRIDGE_RAIL = make_mat("bridge_rail", (0.35, 0.08, 0.05), roughness=0.6)
MAT_SAKURA_TRUNK = make_mat("sakura_trunk", (0.30, 0.18, 0.12), roughness=0.9)
MAT_SAKURA_LEAVES = make_mat("sakura_leaves", (1.0, 0.75, 0.85), roughness=0.7,
                               emi=(0.5, 0.30, 0.40), emi_strength=0.4)
MAT_SAKURA_PETAL = make_mat("sakura_petal", (1.0, 0.65, 0.80), roughness=0.5,
                              emi=(0.8, 0.45, 0.60), emi_strength=0.8)
MAT_BAMBOO_TRUNK = make_mat("bamboo_trunk", (0.35, 0.65, 0.30), roughness=0.7)
MAT_BAMBOO_LEAF = make_mat("bamboo_leaf", (0.20, 0.55, 0.25), roughness=0.8)
MAT_LANTERN_STONE = make_mat("lantern_stone", (0.45, 0.42, 0.38), roughness=0.95)
MAT_LANTERN_LIGHT = make_mat("lantern_light", (1.0, 0.85, 0.55), roughness=0.0, alpha=0.85,
                               emi=(1.0, 0.75, 0.40), emi_strength=4.5)
MAT_WATER = make_mat(
    "water", (0.20, 0.45, 0.55), metallic=0.8, roughness=0.08, alpha=0.85,
    emi=(0.25, 0.55, 0.65), emi_strength=0.5,
)
MAT_KOI_ORANGE = make_mat("koi_orange", (1.0, 0.45, 0.10), roughness=0.5,
                            emi=(0.5, 0.2, 0.05), emi_strength=0.3)
MAT_KOI_WHITE = make_mat("koi_white", (0.95, 0.95, 0.95), roughness=0.5)
MAT_KOI_BLACK = make_mat("koi_black", (0.10, 0.10, 0.10), roughness=0.5)
MAT_PATH_STONE = make_mat("path_stone", (0.50, 0.46, 0.42), roughness=0.85)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 18, 6), mat=MAT_SKY_MORN)
sky.scale = (28, 0.1, 14)

# main ground (gravel + grass patches)
ground = cube("gravel_ground", size=1.0, loc=(0, -0.05, 0), mat=MAT_GRAVEL)
ground.scale = (24, 0.1, 18)

# grass patches around
for i, (gx, gz, gsx, gsz) in enumerate([(-8, 5, 4, 3), (8, -4, 3, 2.5), (-9, -4, 2.5, 2), (7, 6, 2.5, 2)]):
    g = cube(f"grass_{i}", size=1.0, loc=(gx, 0.01, gz), mat=MAT_GRASS)
    g.scale = (gsx, 0.05, gsz)

# 10 raked gravel lines (subtle ridges)
for i in range(10):
    z = -5 + i * 1.0
    line = cube(f"rake_{i}", size=1.0, loc=(0, 0.06, z), mat=MAT_GRAVEL)
    line.scale = (8, 0.03, 0.05)

# --- pagoda 5 étages -------------------------------------------------------
pagoda_p = empty("pagoda", (-5.5, 0, -3.0))

# base platform
base = cube("pag_base", size=1.0, loc=(0, 0.2, 0), parent=pagoda_p, mat=MAT_PAGODA_BEAM)
base.scale = (2.5, 0.4, 2.5)

current_y = 0.45
floor_sizes = [2.0, 1.75, 1.5, 1.25, 1.0]
for i, fs in enumerate(floor_sizes):
    # body (wooden)
    body = cube(f"pag_body_{i}", size=1.0, loc=(0, current_y + 0.45, 0), parent=pagoda_p, mat=MAT_PAGODA_WOOD)
    body.scale = (fs * 0.85, 0.9, fs * 0.85)
    # roof (slightly larger, curved via stretched cone)
    roof_top_r = fs * 0.95
    roof = cone(f"pag_roof_{i}", r1=fs * 1.25, r2=roof_top_r * 0.5, depth=0.55, segs=4, loc=(0, current_y + 1.05, 0), parent=pagoda_p, mat=MAT_PAGODA_ROOF)
    roof.rotation_euler = (math.radians(90), 0, math.radians(45))
    # roof beam ring (lighter wood)
    beam = cube(f"pag_beam_{i}", size=1.0, loc=(0, current_y + 0.85, 0), parent=pagoda_p, mat=MAT_PAGODA_BEAM)
    beam.scale = (fs * 1.1, 0.1, fs * 1.1)
    current_y += 1.3

# spire (sōrin)
spire_p = empty("pag_spire", (0, current_y + 0.2, 0), parent=pagoda_p)
spire_pole = cone("pag_pole", r1=0.07, r2=0.07, depth=1.2, segs=8, loc=(0, 0.6, 0), parent=spire_p, mat=MAT_PAGODA_TOP)
spire_pole.rotation_euler = (math.radians(90), 0, 0)
# 5 rings on spire
for i in range(5):
    rng = cone(f"pag_spire_ring_{i}", r1=0.18 - i * 0.025, r2=0.18 - i * 0.025, depth=0.04, segs=12, loc=(0, 0.3 + i * 0.18, 0), parent=spire_p, mat=MAT_PAGODA_TOP)
    rng.rotation_euler = (math.radians(90), 0, 0)
# spire tip
tip = cone("pag_tip", r1=0.05, r2=0.0, depth=0.4, segs=8, loc=(0, 1.4, 0), parent=spire_p, mat=MAT_PAGODA_TOP)
tip.rotation_euler = (math.radians(90), 0, 0)

# --- water pond + stream ---------------------------------------------------
# central pond
pond = cube("pond", size=1.0, loc=(2.0, 0.05, 1.5), mat=MAT_WATER)
pond.scale = (4.5, 0.1, 3.5)

# stream extending right (under bridge)
stream = cube("stream", size=1.0, loc=(7.0, 0.05, 1.5), mat=MAT_WATER)
stream.scale = (4.5, 0.1, 1.4)

# --- bridge rouge arqué ----------------------------------------------------
bridge_p = empty("bridge", (5.0, 0, 1.5))
# arch deck : multiple cubes following sine arch
N_ARCH = 10
for i in range(N_ARCH):
    t = (i + 0.5) / N_ARCH
    h = math.sin(t * math.pi) * 0.7
    x = -1.5 + t * 3.0
    seg = cube(f"bridge_deck_{i}", size=1.0, loc=(x, 0.5 + h, 0), parent=bridge_p, mat=MAT_BRIDGE_RED)
    seg.scale = (0.32, 0.10, 1.0)
    seg.rotation_euler = (0, 0, math.cos(t * math.pi) * 0.4)

# 2 railings (each side)
for side, z_off in [("L", 0.6), ("R", -0.6)]:
    for i in range(N_ARCH):
        t = (i + 0.5) / N_ARCH
        h = math.sin(t * math.pi) * 0.7
        x = -1.5 + t * 3.0
        # vertical post
        post = cube(f"bridge_post_{side}_{i}", size=1.0, loc=(x, 0.85 + h, z_off), parent=bridge_p, mat=MAT_BRIDGE_RAIL)
        post.scale = (0.06, 0.4, 0.06)
    # top rail (one piece)
    top_rail = cube(f"bridge_rail_{side}", size=1.0, loc=(0, 1.3, z_off), parent=bridge_p, mat=MAT_BRIDGE_RAIL)
    top_rail.scale = (3.4, 0.06, 0.06)

# --- cerisier sakura -------------------------------------------------------
sakura_p = empty("sakura", (-2.0, 0, 4.5))

# trunk : 4 stacked cone segments slightly curving
trunk_y = 0
for i in range(5):
    cone_seg = cone(f"sakura_trunk_{i}", r1=0.30 - i * 0.04, r2=0.28 - i * 0.04, depth=0.7, segs=10, loc=(math.sin(i * 0.5) * 0.1, trunk_y + 0.35, 0), parent=sakura_p, mat=MAT_SAKURA_TRUNK)
    cone_seg.rotation_euler = (math.radians(90), 0, 0)
    trunk_y += 0.7

# 5 main branches outward
for i in range(5):
    a = i * (math.pi * 2 / 5) + 0.4
    bx = math.cos(a) * 0.5
    bz = math.sin(a) * 0.5
    branch = cone(f"sakura_branch_{i}", r1=0.14, r2=0.05, depth=1.2, segs=8, loc=(bx, trunk_y + 0.3, bz), parent=sakura_p, mat=MAT_SAKURA_TRUNK)
    branch.rotation_euler = (math.radians(60), 0, a)

# foliage : 7 puffs of pink leaves
foliage_blobs = []
for i in range(7):
    a = i * (math.pi * 2 / 7)
    fx = math.cos(a) * (0.7 + random.uniform(-0.3, 0.3))
    fz = math.sin(a) * (0.7 + random.uniform(-0.3, 0.3))
    fy = trunk_y + 0.5 + random.uniform(-0.1, 0.2)
    fb = sphere(f"sakura_foliage_{i}", r=0.80, segs=18, rings=14, loc=(fx, fy, fz), parent=sakura_p, mat=MAT_SAKURA_LEAVES)
    fb.scale = (1.2, 0.9, 1.2)
    foliage_blobs.append(fb)

# central main foliage blob
main_blob = sphere("sakura_main_blob", r=1.3, segs=24, rings=18, loc=(0, trunk_y + 0.8, 0), parent=sakura_p, mat=MAT_SAKURA_LEAVES)
main_blob.scale = (1.4, 1.1, 1.4)
foliage_blobs.append(main_blob)

# --- 40 petals falling -----------------------------------------------------
petals = []
for i in range(40):
    px = random.uniform(-4, 0)
    pz = random.uniform(2.5, 6.5)
    py = random.uniform(0.3, 6.5)
    p = cube(f"petal_{i}", size=1.0, loc=(px, py, pz), mat=MAT_SAKURA_PETAL)
    p.scale = (0.08, 0.01, 0.06)
    p.rotation_euler = (random.uniform(0, math.pi), random.uniform(0, math.pi), random.uniform(0, math.pi))
    petals.append((p, px, pz, py, random.uniform(0, 1), random.uniform(0.4, 0.9)))

# --- lanterne tōrō ---------------------------------------------------------
toro_p = empty("toro", (1.0, 0, 4.5))
# base
base = cone("toro_base", r1=0.30, r2=0.25, depth=0.30, segs=8, loc=(0, 0.15, 0), parent=toro_p, mat=MAT_LANTERN_STONE)
base.rotation_euler = (math.radians(90), 0, math.radians(22.5))
# pole
pole = cone("toro_pole", r1=0.10, r2=0.10, depth=0.7, segs=8, loc=(0, 0.65, 0), parent=toro_p, mat=MAT_LANTERN_STONE)
pole.rotation_euler = (math.radians(90), 0, 0)
# lantern body (hex)
body = cone("toro_body", r1=0.30, r2=0.30, depth=0.45, segs=6, loc=(0, 1.20, 0), parent=toro_p, mat=MAT_LANTERN_STONE)
body.rotation_euler = (math.radians(90), 0, 0)
# light inside (sphere émissif)
light = sphere("toro_light", r=0.18, segs=14, rings=10, loc=(0, 1.20, 0), parent=toro_p, mat=MAT_LANTERN_LIGHT)
# roof
roof = cone("toro_roof", r1=0.40, r2=0.05, depth=0.30, segs=6, loc=(0, 1.60, 0), parent=toro_p, mat=MAT_LANTERN_STONE)
roof.rotation_euler = (math.radians(90), 0, 0)
# finial sphere
finial = sphere("toro_finial", r=0.08, segs=10, rings=8, loc=(0, 1.85, 0), parent=toro_p, mat=MAT_LANTERN_STONE)

# --- 3 roches zen ---------------------------------------------------------
for i, (rx, rz, rsy) in enumerate([(-2.0, -3.0, 0.9), (-3.5, -1.5, 0.55), (-1.0, -2.0, 0.4)]):
    r = sphere(f"rock_zen_{i}", r=rsy, segs=14, rings=10, loc=(rx, rsy * 0.6, rz), mat=MAT_ROCK_ZEN)
    r.scale = (1.4, 0.7, 1.0)

# --- 5 bamboos -------------------------------------------------------------
bamboos = []
for i in range(5):
    bx = 6.0 + i * 0.8 + random.uniform(-0.3, 0.3)
    bz = -4.0 + random.uniform(-0.5, 0.5)
    bp = empty(f"bamboo_{i}", (bx, 0, bz))
    height = 3.0 + random.uniform(-0.4, 0.4)
    # 6 segments stacked with subtle nodes
    for j in range(7):
        h = 0.4 + j * 0.5
        seg = cone(f"bamboo_{i}_{j}", r1=0.10 - j * 0.005, r2=0.10 - j * 0.005, depth=0.5, segs=8, loc=(0, h, 0), parent=bp, mat=MAT_BAMBOO_TRUNK)
        seg.rotation_euler = (math.radians(90), 0, 0)
    # 2 leaves at the top
    for k in range(4):
        ka = k * (math.pi * 2 / 4)
        leaf = cube(f"bamboo_{i}_leaf_{k}", size=1.0, loc=(math.cos(ka) * 0.25, height + 0.3, math.sin(ka) * 0.25), parent=bp, mat=MAT_BAMBOO_LEAF)
        leaf.scale = (0.6, 0.02, 0.10)
        leaf.rotation_euler = (math.radians(20), -ka, 0)
    bamboos.append(bp)

# --- 4 koi fish in the pond ------------------------------------------------
def make_koi(name, color_mat, scale=1.0):
    p = empty(name, (0, 0, 0))
    body = sphere(f"{name}_body", r=0.18 * scale, segs=14, rings=10, loc=(0, 0, 0), parent=p, mat=color_mat)
    body.scale = (1.8, 0.6, 0.8)
    # spots on top (smaller different-colored sphere)
    spot1 = sphere(f"{name}_spot1", r=0.08 * scale, segs=8, rings=6, loc=(0.05 * scale, 0.10 * scale, 0), parent=p, mat=MAT_KOI_BLACK if color_mat == MAT_KOI_WHITE else MAT_KOI_WHITE)
    spot1.scale = (1.0, 0.3, 0.8)
    tail = cone(f"{name}_tail", r1=0.10 * scale, r2=0.02 * scale, depth=0.16 * scale, segs=4, loc=(-0.30 * scale, 0, 0), parent=p, mat=color_mat)
    tail.rotation_euler = (0, math.radians(-90), 0)
    tail.scale = (1.0, 1.5, 0.3)
    return p

kois = []
koi_data = [
    (3.0, 0.10, 0.5, MAT_KOI_ORANGE, 1.2),
    (1.5, 0.10, 2.0, MAT_KOI_WHITE, 1.0),
    (2.5, 0.10, 2.5, MAT_KOI_ORANGE, 0.9),
    (0.8, 0.10, 0.8, MAT_KOI_BLACK, 1.1),
]
for i, (kx, ky, kz, color_mat, sc) in enumerate(koi_data):
    k = make_koi(f"koi_{i}", color_mat, sc)
    k.location = (kx, ky, kz)
    k["_x0"] = kx
    k["_z0"] = kz
    k["_a0"] = i * (math.pi / 2)
    k["_r"] = random.uniform(0.6, 1.0)
    kois.append(k)

# --- chemin de pas japonais ------------------------------------------------
for i in range(7):
    sx = -6.0 + i * 1.0
    sz = -2.5 + math.sin(i * 0.6) * 0.4
    st = sphere(f"stepstone_{i}", r=0.30, segs=10, rings=8, loc=(sx, 0.10, sz), mat=MAT_PATH_STONE)
    st.scale = (1.0, 0.25, 0.8)

# --- animation --------------------------------------------------------------

def kf_loc(o, f, l):
    o.location = l
    o.keyframe_insert(data_path="location", frame=f)


def kf_scale(o, f, s):
    o.scale = s
    o.keyframe_insert(data_path="scale", frame=f)


def kf_rot(o, f, r):
    o.rotation_euler = r
    o.keyframe_insert(data_path="rotation_euler", frame=f)


FRAMES = 180

# petals : fall in spiral
for p, px, pz, py_init, ph, spd in petals:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        # fall down with spiral
        angle = local * math.pi * 4.0 * spd
        r = 0.3
        x = px + math.cos(angle) * r
        z = pz + math.sin(angle) * r
        y = py_init - local * 5.5
        if y < 0.05:
            y = 0.05
        kf_loc(p, f, (x, y, z))
        kf_rot(p, f, (local * math.pi * 6 * spd, local * math.pi * 5 * spd, local * math.pi * 4 * spd))

# koi swim curve
for k in kois:
    a0 = k["_a0"]
    r = k["_r"]
    x0 = k["_x0"]
    z0 = k["_z0"]
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        x = x0 + math.cos(angle) * r
        z = z0 + math.sin(angle) * r
        kf_loc(k, f, (x, 0.10, z))
        kf_rot(k, f, (0, -angle + math.pi / 2, math.radians(8) * math.sin(tt * math.pi * 10.0)))

# bamboos sway
for i, bp in enumerate(bamboos):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        bend = math.radians(5) * math.sin(tt * math.pi * 3.0 + phase)
        kf_rot(bp, f, (bend, 0, bend * 0.7))

# sakura main_blob subtle breath
for blob in foliage_blobs:
    base_x = blob.scale.x
    base_y = blob.scale.y
    base_z = blob.scale.z
    phase = id(blob) % 7
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.05 * math.sin(tt * math.pi * 3.0 + phase)
        kf_scale(blob, f, (base_x * s, base_y, base_z * s))

# lantern light pulse
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.20 * math.sin(tt * math.pi * 4.0)
    kf_scale(light, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_jpgarden] wrote {OUT}")
