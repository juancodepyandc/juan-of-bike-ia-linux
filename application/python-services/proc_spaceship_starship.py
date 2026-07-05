"""
proc_spaceship_starship.py — 143e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axis anim).

SpaceX Starship Super Heavy stack en décollage :
- Super Heavy booster bas (cylindre énorme)
- Starship vehicle haut (cylindre + nose cone smooth)
- 33 Raptor engines en cercle (booster) + 6 Raptor engines (Starship)
- 4 grid fins articulées
- 2 forward flaps + 2 aft flaps (Starship)
- 2 windows émissifs (cockpit)
- nose tip
- launch tower Mechazilla (4 piliers + 2 chopstick arms)
- 30 stars background
- 12 flames émissives intense (booster engines firing)
- 60 smoke puffs au sol (exhaust cloud)
- ground concrete pad
- ciel nuit lancement

Animations multi-axes simultanées :
- spaceship : translate Y rising slowly (liftoff) + slight rotate Y
- 33 booster flames : intense pulse haute fréquence
- 6 starship engines : pulse (idle)
- 60 smoke puffs : rise + expand
- 4 grid fins : pivot
- 2 forward flaps + 2 aft flaps : pivot
- 2 chopstick arms (mechazilla) : ouvert
- 30 étoiles scintillent

Sortie : output/3d/pbr_starship_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_starship_proc.glb"))

random.seed(0xCAFE85)

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


def smooth_shade(mesh):
    for poly in mesh.polygons:
        poly.use_smooth = True
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
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
    if smooth:
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


def smooth_cone(name, r1=1.0, r2=0.0, depth=1.0, segs=32, loc=(0, 0, 0), parent=None, mat=None):
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
MAT_SKY_NIGHT = make_mat("sky_night", (0.02, 0.03, 0.08), roughness=1.0,
                          emi=(0.04, 0.05, 0.12), emi_strength=0.4)
MAT_STAR = make_mat("star", (1.0, 1.0, 0.95), roughness=0.0,
                      emi=(1.0, 1.0, 0.95), emi_strength=5.5)
MAT_GROUND_CONCRETE = make_mat("ground", (0.30, 0.30, 0.32), roughness=0.85,
                                 emi=(0.12, 0.12, 0.15), emi_strength=0.4)
MAT_SHIP_SILVER = make_mat("ship_silver", (0.78, 0.80, 0.85), metallic=0.95, roughness=0.20,
                             emi=(0.25, 0.28, 0.32), emi_strength=0.30)
MAT_SHIP_DARK = make_mat("ship_dark", (0.20, 0.22, 0.25), metallic=0.80, roughness=0.35)
MAT_HEAT_SHIELD = make_mat("heat_shield", (0.10, 0.10, 0.12), metallic=0.30, roughness=0.55)
MAT_WINDOW = make_mat("window", (1.0, 0.92, 0.55), roughness=0.0, alpha=0.85,
                        emi=(1.0, 0.92, 0.55), emi_strength=5.0)
MAT_RAPTOR_BELL = make_mat("raptor_bell", (0.55, 0.55, 0.60), metallic=0.95, roughness=0.15)
MAT_RAPTOR_FLAME = make_mat("raptor_flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85,
                              emi=(1.0, 0.55, 0.10), emi_strength=18.0)
MAT_RAPTOR_CORE = make_mat("raptor_core", (1.0, 0.90, 0.40), roughness=0.0,
                             emi=(1.0, 0.90, 0.40), emi_strength=14.0)
MAT_RAPTOR_PLASMA = make_mat("plasma", (0.30, 0.85, 1.0), roughness=0.0, alpha=0.50,
                               emi=(0.30, 0.85, 1.0), emi_strength=10.0)
MAT_SMOKE = make_mat("smoke", (0.65, 0.65, 0.68), roughness=1.0, alpha=0.65,
                       emi=(0.45, 0.45, 0.48), emi_strength=0.4)
MAT_TOWER_METAL = make_mat("tower_metal", (0.55, 0.55, 0.55), metallic=0.85, roughness=0.30,
                             emi=(0.15, 0.15, 0.15), emi_strength=0.25)
MAT_TOWER_LIGHT = make_mat("tower_light", (1.0, 0.30, 0.10), roughness=0.0,
                             emi=(1.0, 0.30, 0.10), emi_strength=10.0)
MAT_GRID_FIN = make_mat("grid_fin", (0.30, 0.30, 0.30), metallic=0.85, roughness=0.40)

# --- backdrop : night sky -----------------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 14, 8), mat=MAT_SKY_NIGHT)

# 30 stars
for i in range(30):
    x = random.uniform(-15, 15)
    z = random.uniform(8, 14)
    y = random.uniform(14, 15)
    r = random.uniform(0.06, 0.11)
    s = smooth_sphere(f"star_{i}", r=r, segs=10, rings=8, loc=(x, y, z), mat=MAT_STAR)
    s["_phase"] = (i * 13) % 47

# --- ground concrete pad -----------------------------------------------
ground = beveled_cube("ground", (30, 0.1, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND_CONCRETE)

# --- Mechazilla launch tower (à droite) ----------------------------
tower_p = empty("tower", (5.5, 0, 0))
# 4 vertical pillars
for k in range(4):
    a = k * (math.pi / 2)
    px = math.cos(a) * 0.6
    pz = math.sin(a) * 0.6
    pillar = smooth_cone(f"tower_pillar_{k}", r1=0.20, r2=0.18, depth=10.0, segs=14, loc=(px, 5.0, pz), parent=tower_p, mat=MAT_TOWER_METAL)
    pillar.rotation_euler = (math.radians(90), 0, 0)
# 4 horizontal supports tying pillars
for h in [2.0, 4.5, 7.0, 9.5]:
    for k in range(4):
        a = k * (math.pi / 2)
        bx = math.cos(a + math.pi / 4) * 0.5
        bz = math.sin(a + math.pi / 4) * 0.5
        beam = beveled_cube(f"tower_beam_{h}_{k}", (0.85, 0.06, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(bx, h, bz), parent=tower_p, mat=MAT_TOWER_METAL)
        beam.rotation_euler = (0, a + math.pi / 4, 0)
# Crosswise diagonal braces (every level)
for h in [3, 5.5, 8]:
    for k in range(4):
        a = k * (math.pi / 2)
        bx = math.cos(a) * 0.6
        bz = math.sin(a) * 0.6
        bar = beveled_cube(f"tower_brace_{h}_{k}", (0.04, 0.06, 0.8), bevel_offset=0.01, bevel_segments=2, loc=(bx * 0.5, h, bz * 0.5), parent=tower_p, mat=MAT_TOWER_METAL)

# 2 chopstick arms (Mechazilla) at top
for side, ang in [("L", math.radians(40)), ("R", math.radians(-40))]:
    arm_p = empty(f"chopstick_{side}", (0, 8.0, 0), parent=tower_p)
    arm_p.rotation_euler = (0, ang, 0)
    arm = smooth_cone(f"chopstick_{side}_arm", r1=0.15, r2=0.10, depth=4.0, segs=14, loc=(2.0, 0, 0), parent=arm_p, mat=MAT_TOWER_METAL)
    arm.rotation_euler = (0, 0, math.radians(90))
    # claw at tip
    claw = beveled_cube(f"chopstick_{side}_claw", (0.30, 0.50, 0.20), bevel_offset=0.05, bevel_segments=3, loc=(3.9, 0, 0), parent=arm_p, mat=MAT_TOWER_METAL)

# Red beacons on tower
for j, h in enumerate([2.5, 5.5, 8.5]):
    beacon = smooth_sphere(f"beacon_{j}", r=0.10, segs=12, rings=8, loc=(0, h, 0.7), parent=tower_p, mat=MAT_TOWER_LIGHT)

# --- SpaceX Starship Super Heavy stack (centered) ---------------------
spacecraft = empty("spacecraft", (0, 0, 0))

# Super Heavy booster (large cylinder bottom)
booster = smooth_cone("super_heavy_booster", r1=1.0, r2=1.0, depth=4.5, segs=40, loc=(0, 2.25, 0), parent=spacecraft, mat=MAT_SHIP_SILVER)
booster.rotation_euler = (math.radians(90), 0, 0)

# booster grid lines (ring details)
for h in [1.0, 2.0, 3.0]:
    ring = smooth_cone(f"booster_ring_{h}", r1=1.03, r2=1.03, depth=0.05, segs=40, loc=(0, h, 0), parent=spacecraft, mat=MAT_SHIP_DARK)
    ring.rotation_euler = (math.radians(90), 0, 0)

# Stage separation ring (where booster meets Starship)
sep_ring = smooth_cone("sep_ring", r1=1.05, r2=1.05, depth=0.15, segs=40, loc=(0, 4.55, 0), parent=spacecraft, mat=MAT_SHIP_DARK)
sep_ring.rotation_euler = (math.radians(90), 0, 0)

# --- 4 grid fins on Super Heavy (animated pivot) -----------------
grid_fins = []
for k in range(4):
    a = k * (math.pi / 2)
    fin_p = empty(f"grid_fin_p_{k}", (math.cos(a) * 1.05, 4.0, math.sin(a) * 1.05), parent=spacecraft)
    fin_p.rotation_euler = (0, a, 0)
    fin = beveled_cube(f"grid_fin_{k}", (0.50, 0.05, 0.60), bevel_offset=0.04, bevel_segments=3, loc=(0.25, 0, 0), parent=fin_p, mat=MAT_GRID_FIN)
    # internal grid pattern (suggested with 4 internal small cubes)
    for ix in range(2):
        for iz in range(2):
            cell = beveled_cube(f"grid_fin_{k}_c_{ix}_{iz}", (0.20, 0.04, 0.25), bevel_offset=0.02, bevel_segments=2, loc=(0.10 + ix * 0.20, 0.01, -0.15 + iz * 0.30), parent=fin_p, mat=MAT_SHIP_DARK)
    grid_fins.append(fin_p)

# --- Starship vehicle (upper stage) --------------------------------
starship_body = smooth_cone("starship_body", r1=1.0, r2=1.0, depth=3.5, segs=40, loc=(0, 6.45, 0), parent=spacecraft, mat=MAT_SHIP_SILVER)
starship_body.rotation_euler = (math.radians(90), 0, 0)

# heat shield (one side, dark tiles)
heat_shield_p = empty("heat_shield_p", (0, 6.45, -0.95), parent=spacecraft)
heat_shield_p.rotation_euler = (math.radians(90), 0, 0)
# rectangular tile section
heat_shield = smooth_cone("heat_shield", r1=0.95, r2=0.95, depth=3.0, segs=40, loc=(0, 0, 0), parent=heat_shield_p, mat=MAT_HEAT_SHIELD)
heat_shield.scale = (1.05, 1.0, 0.7)  # cover only one side via scale

# 2 forward flaps
forward_flaps = []
for side, dz in [("L", 0.95), ("R", -0.95)]:
    flap_p = empty(f"forward_flap_{side}", (0, 7.50, dz), parent=spacecraft)
    flap = beveled_cube(f"forward_flap_{side}_b", (0.6, 0.06, 0.5), bevel_offset=0.04, bevel_segments=3, loc=(0, 0, 0.3 if side == "L" else -0.3), parent=flap_p, mat=MAT_SHIP_SILVER)
    forward_flaps.append(flap_p)

# 2 aft flaps (larger, near bottom of Starship)
aft_flaps = []
for side, dz in [("L", 0.95), ("R", -0.95)]:
    flap_p = empty(f"aft_flap_{side}", (0, 5.0, dz), parent=spacecraft)
    flap = beveled_cube(f"aft_flap_{side}_b", (0.85, 0.08, 0.7), bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0.4 if side == "L" else -0.4), parent=flap_p, mat=MAT_SHIP_SILVER)
    aft_flaps.append(flap_p)

# nose cone (smooth tapered)
nose = smooth_cone("nose", r1=1.0, r2=0.05, depth=2.5, segs=40, loc=(0, 9.45, 0), parent=spacecraft, mat=MAT_SHIP_SILVER)
nose.rotation_euler = (math.radians(90), 0, 0)

# 2 windows (cockpit) sur Starship
for side, dz in [("L", 0.95), ("R", -0.95)]:
    w = smooth_sphere(f"window_{side}", r=0.20, segs=18, rings=14, loc=(0, 7.8, dz), parent=spacecraft, mat=MAT_WINDOW, scale=(0.4, 0.7, 1.0))

# nose tip light
nose_tip = smooth_sphere("nose_tip", r=0.12, segs=14, rings=10, loc=(0, 10.5, 0), parent=spacecraft, mat=MAT_TOWER_LIGHT)

# --- 33 Raptor engines on booster (3 rings: 13 outer + 10 middle + 10 inner) ----
booster_flames = []
def make_engine(name, x, y, z, parent, scale=1.0):
    # bell (chrome cone)
    bell = smooth_cone(f"{name}_bell", r1=0.10 * scale, r2=0.16 * scale, depth=0.30 * scale, segs=16, loc=(x, y, z), parent=parent, mat=MAT_RAPTOR_BELL)
    # flame (large sphere stretched)
    flame = smooth_sphere(f"{name}_flame", r=0.18 * scale, segs=18, rings=12, loc=(x, y - 0.40 * scale, z), parent=parent, mat=MAT_RAPTOR_FLAME, scale=(1.0, 2.2, 1.0))
    # plasma core (inner)
    core = smooth_sphere(f"{name}_core", r=0.10 * scale, segs=14, rings=10, loc=(x, y - 0.30 * scale, z), parent=parent, mat=MAT_RAPTOR_CORE, scale=(1.0, 2.5, 1.0))
    # plasma diamond shock pattern
    diamond = smooth_sphere(f"{name}_diamond", r=0.06 * scale, segs=12, rings=8, loc=(x, y - 0.70 * scale, z), parent=parent, mat=MAT_RAPTOR_PLASMA, scale=(0.7, 1.5, 0.7))
    return flame, core, diamond

# Outer ring : 13 engines
for k in range(13):
    a = k * (math.pi * 2 / 13)
    x = math.cos(a) * 0.85
    z = math.sin(a) * 0.85
    flame, core, diamond = make_engine(f"raptor_out_{k}", x, 0.05, z, spacecraft)
    booster_flames.append(flame)

# Middle ring : 10 engines
for k in range(10):
    a = k * (math.pi * 2 / 10) + (math.pi / 10)
    x = math.cos(a) * 0.55
    z = math.sin(a) * 0.55
    flame, core, diamond = make_engine(f"raptor_mid_{k}", x, 0.05, z, spacecraft)
    booster_flames.append(flame)

# Inner center : 10 engines (with vacuum bells - bigger)
for k in range(10):
    a = k * (math.pi * 2 / 10)
    x = math.cos(a) * 0.25
    z = math.sin(a) * 0.25
    flame, core, diamond = make_engine(f"raptor_in_{k}", x, 0.05, z, spacecraft, scale=1.2)
    booster_flames.append(flame)

# --- 6 Raptor engines on Starship (at base of upper stage) -----------
starship_engines = []
for k in range(6):
    a = k * (math.pi * 2 / 6)
    x = math.cos(a) * 0.55
    z = math.sin(a) * 0.55
    bell = smooth_cone(f"ss_eng_{k}_bell", r1=0.08, r2=0.13, depth=0.25, segs=14, loc=(x, 4.65, z), parent=spacecraft, mat=MAT_RAPTOR_BELL)
    # idle flame (small)
    flame = smooth_sphere(f"ss_eng_{k}_flame", r=0.10, segs=14, rings=10, loc=(x, 4.45, z), parent=spacecraft, mat=MAT_RAPTOR_FLAME, scale=(1.0, 1.5, 1.0))
    starship_engines.append(flame)

# --- 60 smoke puffs au sol (massive exhaust cloud) -----------------
smoke_puffs = []
for i in range(60):
    a = random.uniform(0, math.pi * 2)
    r = random.uniform(0.5, 4.0)
    sx = math.cos(a) * r
    sz = math.sin(a) * r
    sy = random.uniform(0.1, 2.5)
    pr = random.uniform(0.30, 0.70)
    puff = smooth_sphere(f"smoke_{i}", r=pr, segs=14, rings=10, loc=(sx, sy, sz), mat=MAT_SMOKE, scale=(1.2, 1.0, 1.2))
    smoke_puffs.append((puff, sx, sz, sy, pr, random.uniform(0, 1)))

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

# spacecraft : rises slowly + slight rotate Y
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    by = tt * 1.5  # rises 1.5m over loop
    rotY = math.radians(2) * math.sin(tt * math.pi * 2.0)
    kf_loc(spacecraft, f, (0, by, 0))
    kf_rot(spacecraft, f, (0, rotY, 0))

# 33 booster flames pulse intense high-frequency
for i, flame in enumerate(booster_flames):
    phase = i * 0.1
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 14.0 + phase)
        kf_scale(flame, f, (s, 2.2 * s, s))

# 6 starship engines pulse
for flame in starship_engines:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 7.0)
        kf_scale(flame, f, (s, 1.5 * s, s))

# 60 smoke puffs : expand + rise + drift outward
for puff, sx, sz, sy_init, pr_init, ph in smoke_puffs:
    base_dir = math.atan2(sz, sx)
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        local = (tt + ph) % 1.0
        # rise + outward
        dy = sy_init + local * 4.0
        out = 1.0 + local * 1.5
        dx = sx * out
        dz = sz * out
        kf_loc(puff, f, (dx, dy, dz))
        s = 1.0 + local * 2.0
        kf_scale(puff, f, (s, s, s))

# 4 grid fins pivot
for i, fin_p in enumerate(grid_fins):
    base_rot = fin_p.rotation_euler.copy()
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(20) * math.sin(tt * math.pi * 3.0 + i * 0.5)
        kf_rot(fin_p, f, (delta, base_rot[1], 0))

# 2 forward flaps pivot
for i, flap_p in enumerate(forward_flaps):
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(15) * math.sin(tt * math.pi * 2.5)
        kf_rot(flap_p, f, (delta, 0, 0))

# 2 aft flaps pivot
for i, flap_p in enumerate(aft_flaps):
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        delta = math.radians(20) * math.cos(tt * math.pi * 2.5 + i * 0.5)
        kf_rot(flap_p, f, (delta, 0, 0))

# stars twinkle
for i in range(30):
    star = bpy.data.objects.get(f"star_{i}")
    if not star:
        continue
    phase = star["_phase"]
    for f in range(1, FRAMES + 1, 6):
        tt = (f - 1) / (FRAMES - 1)
        local = (math.sin(tt * math.pi * 6.0 + phase * 0.13) + 1) * 0.5
        s = 0.7 + 0.5 * local
        kf_scale(star, f, (s, s, s))

# tower beacons pulse
for j in range(3):
    beacon = bpy.data.objects.get(f"beacon_{j}")
    if beacon:
        for f in range(1, FRAMES + 1, 2):
            tt = (f - 1) / (FRAMES - 1)
            s = 1.0 + 0.25 * math.sin(tt * math.pi * 8.0 + j * 0.4)
            kf_scale(beacon, f, (s, s, s))

# nose tip pulse
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.20 * math.sin(tt * math.pi * 10.0)
    kf_scale(nose_tip, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_starship] wrote {OUT}")
