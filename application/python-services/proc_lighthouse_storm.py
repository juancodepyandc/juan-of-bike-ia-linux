"""
proc_lighthouse_storm.py — 126e procédural AuroraIA, Phase F++++.

Phare dans une tempête : phare cylindrique rayé rouge/blanc avec
lanterne tournante émissive + faisceau rotatif + falaise rocheuse
+ 12 vagues océan ondulantes + 6 éclairs zigzag flash + nuages noirs
orageux + 30 gouttes pluie tombant + bateau en détresse au loin
pitchant + 3 mouettes volantes + écume sur les vagues.

Animation :
- lanterne phare rotate Y (rapide)
- faisceau (cone) rotate avec lanterne
- 12 vagues : ondulent (sin Y)
- 6 éclairs : flash Gaussian pulse (alpha + scale)
- 30 gouttes pluie : tombent en boucle
- bateau : pitch + roll
- 3 mouettes : volent en arcs

Sortie : output/3d/pbr_lighthousestorm_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_lighthousestorm_proc.glb"))

random.seed(0xB0A77F)

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
MAT_SKY_STORM = make_mat("sky_storm", (0.10, 0.10, 0.13), roughness=1.0,
                          emi=(0.08, 0.08, 0.12), emi_strength=0.3)
MAT_CLOUD_DARK = make_mat("cloud_dark", (0.15, 0.15, 0.18), roughness=1.0, alpha=0.85,
                            emi=(0.10, 0.10, 0.15), emi_strength=0.3)
MAT_OCEAN = make_mat(
    "ocean", (0.05, 0.10, 0.18), metallic=0.85, roughness=0.15, alpha=0.95,
    emi=(0.05, 0.10, 0.20), emi_strength=0.3,
)
MAT_WAVE = make_mat(
    "wave", (0.20, 0.30, 0.40), metallic=0.7, roughness=0.2, alpha=0.85,
    emi=(0.15, 0.25, 0.35), emi_strength=0.4,
)
MAT_FOAM = make_mat(
    "foam", (0.95, 0.95, 1.0), roughness=0.4, alpha=0.85,
    emi=(0.85, 0.90, 1.0), emi_strength=1.5,
)
MAT_CLIFF = make_mat("cliff", (0.30, 0.27, 0.22), roughness=0.95)
MAT_CLIFF_DARK = make_mat("cliff_dark", (0.18, 0.16, 0.13), roughness=0.95)
MAT_LIGHTHOUSE_R = make_mat("lh_red", (0.85, 0.10, 0.10), roughness=0.6,
                              emi=(0.35, 0.05, 0.05), emi_strength=0.3)
MAT_LIGHTHOUSE_W = make_mat("lh_white", (0.95, 0.95, 0.92), roughness=0.6,
                              emi=(0.40, 0.40, 0.38), emi_strength=0.3)
MAT_LIGHTHOUSE_TOP = make_mat("lh_top", (0.10, 0.08, 0.06), roughness=0.7)
MAT_LIGHTHOUSE_GLASS = make_mat(
    "lh_glass", (1.0, 0.95, 0.65), roughness=0.0, alpha=0.85,
    emi=(1.0, 0.95, 0.65), emi_strength=10.0,
)
MAT_LIGHTHOUSE_RAIL = make_mat("lh_rail", (0.35, 0.35, 0.35), metallic=0.7, roughness=0.4)
MAT_LIGHT_BEAM = make_mat(
    "beam", (1.0, 0.95, 0.65), roughness=0.0, alpha=0.20,
    emi=(1.0, 0.95, 0.65), emi_strength=4.0,
)
MAT_LIGHTNING = make_mat(
    "lightning", (1.0, 0.95, 1.0), roughness=0.0, alpha=0.90,
    emi=(1.0, 0.95, 1.0), emi_strength=12.0,
)
MAT_RAIN = make_mat(
    "rain", (0.65, 0.75, 0.85), roughness=0.0, alpha=0.55,
    emi=(0.55, 0.70, 0.85), emi_strength=1.8,
)
MAT_BOAT_HULL = make_mat("boat_hull", (0.35, 0.20, 0.10), roughness=0.65,
                           emi=(0.15, 0.08, 0.04), emi_strength=0.2)
MAT_BOAT_MAST = make_mat("boat_mast", (0.20, 0.15, 0.08), roughness=0.7)
MAT_BOAT_SAIL = make_mat("boat_sail", (0.80, 0.78, 0.72), roughness=0.85, alpha=0.95,
                           emi=(0.30, 0.28, 0.25), emi_strength=0.3)
MAT_BOAT_LIGHT = make_mat("boat_light", (1.0, 0.45, 0.10), roughness=0.0,
                            emi=(1.0, 0.45, 0.10), emi_strength=7.0)
MAT_GULL = make_mat("gull", (0.85, 0.85, 0.88), roughness=0.7,
                      emi=(0.40, 0.40, 0.42), emi_strength=0.2)

# --- backdrop ---------------------------------------------------------------
sky = cube("sky_back", size=1.0, loc=(0, 16, 6), mat=MAT_SKY_STORM)
sky.scale = (32, 0.1, 14)

# 8 dark storm clouds
for i in range(8):
    cx = -14 + i * 4 + random.uniform(-1, 1)
    cz = 10 + random.uniform(-0.5, 1.5)
    cy = 14 + random.uniform(-0.5, 0.5)
    cl = sphere(f"cloud_{i}", r=random.uniform(1.2, 1.8), segs=16, rings=10, loc=(cx, cy, cz), mat=MAT_CLOUD_DARK)
    cl.scale = (1.6, 0.6, 1.1)

# --- ocean surface ----------------------------------------------------------
ocean = cube("ocean", size=1.0, loc=(0, 0, 0), mat=MAT_OCEAN)
ocean.scale = (40, 0.1, 28)

# 12 wave crests
waves = []
for i in range(12):
    wx = random.uniform(-15, 15)
    wz = random.uniform(-10, 10)
    w = sphere(f"wave_{i}", r=random.uniform(0.6, 1.0), segs=16, rings=10, loc=(wx, 0.3, wz), mat=MAT_WAVE)
    w.scale = (2.0, 0.3, 1.2)
    waves.append((w, wx, wz, random.uniform(0, math.pi * 2)))

# foam on top of some waves
foams = []
for i in range(6):
    wx = random.uniform(-12, 12)
    wz = random.uniform(-8, 8)
    fo = sphere(f"foam_{i}", r=0.5, segs=12, rings=8, loc=(wx, 0.55, wz), mat=MAT_FOAM)
    fo.scale = (1.4, 0.15, 0.8)
    foams.append((fo, wx, wz, random.uniform(0, 1)))

# --- cliff (rocky base for lighthouse) ------------------------------------
cliff_p = empty("cliff_p", (-2.0, 0, 0))

# main rock mass
main_rock = cube("cliff_main", size=1.0, loc=(0, 0.8, 0), parent=cliff_p, mat=MAT_CLIFF)
main_rock.scale = (4.0, 1.6, 3.0)
# top platform (lighter, flatter)
top = cube("cliff_top", size=1.0, loc=(0, 1.65, 0), parent=cliff_p, mat=MAT_CLIFF_DARK)
top.scale = (3.0, 0.1, 2.5)
# 4 lower rocks (jagged)
for i, (rx, rz, h) in enumerate([(-2.5, 1.5, 0.8), (2.5, 1.5, 1.0), (-2.5, -1.5, 0.6), (2.5, -1.5, 0.7)]):
    r = sphere(f"cliff_rock_{i}", r=0.6, segs=12, rings=8, loc=(rx, h * 0.5, rz), parent=cliff_p, mat=MAT_CLIFF)
    r.scale = (1.2, h, 0.9)

# --- lighthouse tower -----------------------------------------------------
lh_p = empty("lighthouse", (-2.0, 1.7, 0))

# 6 alternating red/white stripes
for i in range(6):
    y = 0.5 + i * 0.8
    mat = MAT_LIGHTHOUSE_R if i % 2 == 0 else MAT_LIGHTHOUSE_W
    seg = cone(f"lh_seg_{i}", r1=0.65 - i * 0.04, r2=0.60 - i * 0.04, depth=0.8, segs=16, loc=(0, y, 0), parent=lh_p, mat=mat)
    seg.rotation_euler = (math.radians(90), 0, 0)

# lantern room base (gallery)
gallery = cone("lh_gallery", r1=0.55, r2=0.55, depth=0.20, segs=16, loc=(0, 5.25, 0), parent=lh_p, mat=MAT_LIGHTHOUSE_TOP)
gallery.rotation_euler = (math.radians(90), 0, 0)
# 8 railing posts on gallery
for i in range(8):
    a = i * (math.pi * 2 / 8)
    rp = cube(f"lh_railing_{i}", size=1.0, loc=(math.cos(a) * 0.55, 5.45, math.sin(a) * 0.55), parent=lh_p, mat=MAT_LIGHTHOUSE_RAIL)
    rp.scale = (0.03, 0.2, 0.03)

# lantern room (glass dome)
lantern_p = empty("lantern", (0, 5.7, 0), parent=lh_p)
lantern_body = cone("lantern_body", r1=0.42, r2=0.42, depth=0.5, segs=12, loc=(0, 0, 0), parent=lantern_p, mat=MAT_LIGHTHOUSE_GLASS)
lantern_body.rotation_euler = (math.radians(90), 0, 0)
# 8 vertical glass bars
for i in range(8):
    a = i * (math.pi * 2 / 8)
    bar = cube(f"lantern_bar_{i}", size=1.0, loc=(math.cos(a) * 0.42, 0, math.sin(a) * 0.42), parent=lantern_p, mat=MAT_LIGHTHOUSE_RAIL)
    bar.scale = (0.03, 0.5, 0.03)

# roof (cone)
roof = cone("lh_roof", r1=0.50, r2=0.05, depth=0.45, segs=16, loc=(0, 6.20, 0), parent=lh_p, mat=MAT_LIGHTHOUSE_TOP)
roof.rotation_euler = (math.radians(90), 0, 0)
# top sphere finial
finial = sphere("lh_finial", r=0.08, segs=10, rings=8, loc=(0, 6.55, 0), parent=lh_p, mat=MAT_LIGHTHOUSE_TOP)

# light beam (4 cones rotating, simulating rotating Fresnel lens)
beam_p = empty("beam_p", (0, 5.7, 0), parent=lh_p)
beams = []
for i in range(2):
    a = i * math.pi  # 2 opposing beams
    beam = cone(f"beam_{i}", r1=0.05, r2=2.5, depth=12.0, segs=16, loc=(math.cos(a) * 6, 0, math.sin(a) * 6), parent=beam_p, mat=MAT_LIGHT_BEAM)
    beam.rotation_euler = (math.radians(90), 0, a - math.pi / 2)
    beams.append(beam)

# door at base
door = cube("lh_door", size=1.0, loc=(0, 0.50, 0.65), parent=lh_p, mat=MAT_LIGHTHOUSE_TOP)
door.scale = (0.25, 0.40, 0.04)

# 2 small windows along the tower
for i, wy in enumerate([2.0, 3.5]):
    win = cube(f"lh_window_{i}", size=1.0, loc=(0, wy, 0.62), parent=lh_p, mat=MAT_LIGHTHOUSE_GLASS)
    win.scale = (0.15, 0.20, 0.05)

# --- 6 éclairs zigzag flash ------------------------------------------------
lightnings = []
def make_lightning(name, x_top, z_top):
    p = empty(name, (x_top, 12, z_top))
    # 5 zigzag segments
    cy = 0
    cx = 0
    for j in range(5):
        ny = cy - 2.0
        nx = cx + random.uniform(-0.5, 0.5)
        # segment between (cx, cy) and (nx, ny)
        mx = (cx + nx) / 2
        my = (cy + ny) / 2
        dx = nx - cx
        dy = ny - cy
        length = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)
        seg = cube(f"{name}_{j}", size=1.0, loc=(mx, my, 0), parent=p, mat=MAT_LIGHTNING)
        seg.scale = (length, 0.10, 0.10)
        seg.rotation_euler = (0, 0, angle)
        cx, cy = nx, ny
    return p

for i in range(6):
    x_top = random.uniform(-12, 12)
    z_top = random.uniform(-2, 8)
    l = make_lightning(f"lightning_{i}", x_top, z_top)
    lightnings.append((l, i))

# --- 30 gouttes de pluie ---------------------------------------------------
rain_drops = []
for i in range(30):
    rx = random.uniform(-15, 15)
    rz = random.uniform(-10, 10)
    ry = random.uniform(2, 12)
    d = cube(f"rain_{i}", size=1.0, loc=(rx, ry, rz), mat=MAT_RAIN)
    d.scale = (0.02, 0.20, 0.02)
    d.rotation_euler = (math.radians(15), 0, math.radians(5))
    rain_drops.append((d, rx, rz, ry, random.uniform(0, 1)))

# --- bateau en détresse (far away in the storm) ---------------------------
boat_p = empty("boat", (8.0, 0.5, 4.0))
# hull (curved)
hull = sphere("boat_hull", r=0.55, segs=16, rings=10, loc=(0, 0, 0), parent=boat_p, mat=MAT_BOAT_HULL)
hull.scale = (1.6, 0.6, 0.8)
# top deck
deck = cube("boat_deck", size=1.0, loc=(0, 0.20, 0), parent=boat_p, mat=MAT_BOAT_HULL)
deck.scale = (1.3, 0.06, 0.6)
# mast
mast = cone("boat_mast", r1=0.04, r2=0.03, depth=1.6, segs=6, loc=(0, 0.95, 0), parent=boat_p, mat=MAT_BOAT_MAST)
mast.rotation_euler = (math.radians(90), 0, 0)
# torn sail (small)
sail = cube("boat_sail", size=1.0, loc=(0.20, 0.95, 0), parent=boat_p, mat=MAT_BOAT_SAIL)
sail.scale = (0.30, 0.7, 0.02)
sail.rotation_euler = (0, 0, math.radians(-25))
# distress light (red blinking)
light_boat = sphere("boat_light", r=0.06, segs=8, rings=6, loc=(0, 1.75, 0), parent=boat_p, mat=MAT_BOAT_LIGHT)

# --- 3 mouettes flying ----------------------------------------------------
gulls = []
for i in range(3):
    a = i * (math.pi * 2 / 3) + 0.5
    r = 5.0
    bx = math.cos(a) * r
    bz = math.sin(a) * r
    by = 6.0 + random.uniform(-1.0, 1.0)
    bp = empty(f"gull_{i}", (bx, by, bz))
    body = sphere(f"gull_{i}_body", r=0.12, segs=10, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_GULL)
    body.scale = (1.4, 0.7, 1.0)
    # 2 wings stretched
    for side, xx in (("L", -0.30), ("R", 0.30)):
        w = cube(f"gull_{i}_w_{side}", size=1.0, loc=(xx, 0, 0), parent=bp, mat=MAT_GULL)
        w.scale = (0.30, 0.02, 0.12)
    gulls.append((bp, a, r, by))

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

# lighthouse beam rotates
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    kf_rot(beam_p, f, (0, tt * math.pi * 4.0, 0))  # 2 turns/loop (slow Fresnel)

# waves ondulate
for w, wx, wz, ph in waves:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dy = 0.3 + 0.4 * math.sin(tt * math.pi * 4.0 + ph)
        kf_loc(w, f, (wx, dy, wz))
        s = 1.0 + 0.15 * math.cos(tt * math.pi * 3.0 + ph)
        kf_scale(w, f, (2.0 * s, 0.3, 1.2 * s))

# foam dance
for fo, fx, fz, ph in foams:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        dy = 0.55 + 0.20 * math.sin(tt * math.pi * 5.0 + ph)
        s = 1.0 + 0.25 * math.sin(tt * math.pi * 6.0 + ph)
        kf_loc(fo, f, (fx, dy, fz))
        kf_scale(fo, f, (1.4 * s, 0.15, 0.8 * s))

# lightning flashes (random short bursts)
for l, idx in lightnings:
    phase = idx * 20
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 90
        lt = local_f / 90
        # very sharp pulse near lt=0.1 only
        if lt < 0.15:
            s = 1.5 * math.exp(-((lt - 0.05) * 30.0) ** 2)
        else:
            s = 0.0
        kf_scale(l, f, (s, s, s))

# rain falls (linear loop)
for d, rx, rz, ry_init, ph in rain_drops:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        ry = ry_init - local * 12.0
        if ry < 0.1:
            ry = 0.1
        kf_loc(d, f, (rx, ry, rz))

# boat pitch + roll
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    pitch = math.radians(10) * math.sin(tt * math.pi * 3.0)
    roll = math.radians(8) * math.cos(tt * math.pi * 2.5)
    by = 0.5 + 0.3 * math.sin(tt * math.pi * 3.0)
    kf_loc(boat_p, f, (8.0, by, 4.0))
    kf_rot(boat_p, f, (pitch, 0, roll))

# boat distress light blink
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    on = math.sin(tt * math.pi * 6.0) > 0
    s = 1.5 if on else 0.4
    kf_scale(light_boat, f, (s, s, s))

# 3 gulls fly
for bp, a0, r, by in gulls:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        angle = a0 + tt * math.pi * 2.0
        bx = math.cos(angle) * r
        bz = math.sin(angle) * r
        by_a = by + 0.4 * math.sin(tt * math.pi * 4.0 + a0)
        kf_loc(bp, f, (bx, by_a, bz))
        kf_rot(bp, f, (0, -angle + math.pi / 2, math.radians(18) * math.sin(tt * math.pi * 8.0)))

# lantern body pulse (the rotating fresnel actually emits)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.10 * math.sin(tt * math.pi * 5.0)
    kf_scale(lantern_body, f, (s, 1.0, s))

# clouds drift slow
for i in range(8):
    cl = bpy.data.objects.get(f"cloud_{i}")
    if not cl:
        continue
    base_x = cl.location.x
    base_z = cl.location.z
    for f in range(1, FRAMES + 1, 5):
        tt = (f - 1) / (FRAMES - 1)
        dx = base_x + 0.5 * math.sin(tt * math.pi * 1.5 + i * 0.6)
        dz = base_z + 0.3 * math.cos(tt * math.pi * 1.2 + i * 0.4)
        kf_loc(cl, f, (dx, cl.location.y, dz))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_lighthousestorm] wrote {OUT}")
