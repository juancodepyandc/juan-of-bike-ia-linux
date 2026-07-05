"""
proc_steampunk_clock_tower.py — 156e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Tour horloge steampunk avec engrenages exposés et vapeur :
- 2 tours en pierre bevelée multi-étages (5 niveaux principal + 3 secondaire)
- Grande horloge centrale face cuivre + 12 chiffres romains + 2 aiguilles bevelées + sub-cadran secondes
- 8 engrenages cogs métal visibles différentes tailles
- 4 cheminées avec vapeur émissive cyclique
- 6 tuyaux cuivre interconnectés
- 12 ampoules edison émissives (orange chaud)
- pont reliant 2 tours
- petit dirigeable amarré
- 4 drapeaux flottants
- ciel orange vapeur
- 3 nuages
- soleil émissif
- horloge mécanique fonctionnelle (heure/minute/seconde)

Animations multi-axes simultanées :
- 8 engrenages tournent rates différents (axiaux Z)
- 3 aiguilles horloge tournent (heure/minute/seconde séparées)
- vapeur monte 4 cheminées cyclique
- 12 ampoules pulse différentielles
- dirigeable bob + sway
- 4 drapeaux flottent ondulation
- 3 nuages drift
- soleil pulse

Sortie : output/3d/pbr_clocktower_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_clocktower_proc.glb"))

random.seed(0xCEC101)


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


def smooth_torus(name, r1=1.0, r2=0.2, major_segs=24, minor_segs=12, loc=(0, 0, 0), parent=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, segments=major_segs, radius=r1, cap_ends=False)
    # extrude minor radius — simpler: use built-in via bpy.ops
    bm.free()
    # Use bpy primitive instead
    bpy.ops.mesh.primitive_torus_add(major_radius=r1, minor_radius=r2, major_segments=major_segs, minor_segments=minor_segs, location=loc)
    o = bpy.context.object
    o.name = name
    if parent:
        o.parent = parent
    if mat:
        o.data.materials.append(mat)
    smooth_shade(o.data)
    return o


# --- materials --------------------------------------------------------------
MAT_SKY_ORANGE = make_mat("sky_orange", (0.85, 0.45, 0.25), roughness=1.0, emi=(0.65, 0.30, 0.18), emi_strength=1.0)
MAT_SUN = make_mat("sun", (1.0, 0.85, 0.40), roughness=0.0, emi=(1.0, 0.85, 0.40), emi_strength=12.0)
MAT_SUN_HALO = make_mat("sun_halo", (1.0, 0.85, 0.40), roughness=0.0, alpha=0.30, emi=(1.0, 0.85, 0.40), emi_strength=3.0)
MAT_CLOUD = make_mat("cloud", (0.92, 0.82, 0.70), roughness=1.0, alpha=0.65, emi=(0.50, 0.40, 0.35), emi_strength=0.4)
MAT_STONE = make_mat("stone", (0.45, 0.42, 0.38), roughness=0.85)
MAT_STONE_DARK = make_mat("stone_dark", (0.30, 0.27, 0.24), roughness=0.95)
MAT_BRICK = make_mat("brick", (0.55, 0.30, 0.20), roughness=0.85)
MAT_COPPER = make_mat("copper", (0.85, 0.50, 0.30), metallic=0.85, roughness=0.30, emi=(0.30, 0.18, 0.12), emi_strength=0.3)
MAT_COPPER_DARK = make_mat("copper_dark", (0.55, 0.32, 0.20), metallic=0.85, roughness=0.45)
MAT_GOLD = make_mat("gold", (0.95, 0.75, 0.30), metallic=0.95, roughness=0.20, emi=(0.45, 0.35, 0.15), emi_strength=0.5)
MAT_IRON = make_mat("iron", (0.45, 0.40, 0.40), metallic=0.85, roughness=0.55)
MAT_CLOCK_FACE = make_mat("clock_face", (0.92, 0.85, 0.65), roughness=0.40, emi=(0.35, 0.30, 0.20), emi_strength=0.8)
MAT_CLOCK_HAND = make_mat("clock_hand", (0.20, 0.15, 0.10), metallic=0.50, roughness=0.40)
MAT_NUMERAL = make_mat("numeral", (0.15, 0.10, 0.08), metallic=0.20, roughness=0.40)
MAT_STEAM = make_mat("steam", (0.85, 0.78, 0.70), roughness=1.0, alpha=0.40, emi=(0.55, 0.50, 0.45), emi_strength=1.5)
MAT_EDISON = make_mat("edison", (1.0, 0.65, 0.20), roughness=0.0, emi=(1.0, 0.65, 0.20), emi_strength=11.0)
MAT_BULB_GLASS = make_mat("bulb_glass", (1.0, 0.90, 0.65), roughness=0.10, alpha=0.45, emi=(1.0, 0.80, 0.40), emi_strength=2.0)
MAT_FLAG = make_mat("flag", (0.75, 0.20, 0.20), roughness=0.7, emi=(0.30, 0.05, 0.05), emi_strength=0.4)
MAT_DIRIGIBLE = make_mat("dirigible", (0.65, 0.55, 0.45), roughness=0.5)
MAT_DIRIGIBLE_TRIM = make_mat("dirigible_trim", (0.85, 0.55, 0.20), metallic=0.7, roughness=0.30)
MAT_ROOF = make_mat("roof", (0.45, 0.20, 0.18), roughness=0.75)
MAT_GROUND = make_mat("ground", (0.20, 0.15, 0.12), roughness=0.95)


# --- backdrop : steampunk orange sky ---------------------------------------
sky = beveled_cube("sky_back", (45, 0.2, 22), bevel_offset=0.05, bevel_segments=2, loc=(0, 16, 10), mat=MAT_SKY_ORANGE)
ground = beveled_cube("ground", (30, 0.1, 20), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_GROUND)

# sun + halos
sun_p = empty("sun_p", (10, 13, 6))
sun = smooth_sphere("sun", r=1.3, segs=28, rings=18, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN)
sun_halo_1 = smooth_sphere("sun_halo_1", r=2.0, segs=22, rings=14, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)
sun_halo_2 = smooth_sphere("sun_halo_2", r=2.8, segs=20, rings=12, loc=(0, 0, 0), parent=sun_p, mat=MAT_SUN_HALO)

# 3 clouds drift
clouds = []
for ck in range(3):
    cp = empty(f"cloud_{ck}", (random.uniform(-12, 12), random.uniform(11, 14), random.uniform(4, 9)))
    clouds.append(cp)
    for j in range(4):
        smooth_sphere(f"cloud_{ck}_p_{j}", r=random.uniform(0.7, 1.1), segs=18, rings=12, loc=(random.uniform(-0.8, 0.8), random.uniform(-0.15, 0.2), random.uniform(-0.6, 0.6)), parent=cp, mat=MAT_CLOUD, scale=(1.0, 0.6, 1.0))
    cp["_base_x"] = cp.location.x
    cp["_speed"] = random.uniform(0.6, 1.0)


# --- main tower (5 stages) -------------------------------------------------
main_tower_p = empty("main_tower", (-3.5, 0, 0))
# stages : decreasing radius going up
STAGE_HEIGHTS = [3.5, 3.0, 2.8, 2.5, 2.2]  # heights
STAGE_RADII = [1.6, 1.4, 1.3, 1.2, 1.0]
cur_y = 0
for sg, (h, r) in enumerate(zip(STAGE_HEIGHTS, STAGE_RADII)):
    mat = MAT_STONE if sg % 2 == 0 else MAT_STONE_DARK
    stage = smooth_cone(f"main_stage_{sg}", r1=r, r2=r * 0.92, depth=h, segs=14, loc=(0, cur_y + h / 2, 0), parent=main_tower_p, mat=mat)
    # decorative band copper at top of each stage
    band = smooth_torus(f"main_band_{sg}", r1=r * 1.02, r2=0.08, major_segs=24, minor_segs=8, loc=(0, cur_y + h - 0.10, 0), parent=main_tower_p, mat=MAT_COPPER)
    band.rotation_euler = (math.radians(90), 0, 0)
    cur_y += h
# crowning roof (cone pointu)
roof_p = empty("main_roof_p", (0, cur_y, 0), parent=main_tower_p)
smooth_cone("main_roof", r1=1.05, r2=0.0, depth=2.5, segs=14, loc=(0, 1.25, 0), parent=roof_p, mat=MAT_ROOF)
# golden ball at top
smooth_sphere("main_ball", r=0.18, segs=18, rings=12, loc=(0, 2.65, 0), parent=roof_p, mat=MAT_GOLD)
# flag pole + flag
smooth_cone("main_pole", r1=0.04, r2=0.04, depth=0.8, segs=8, loc=(0, 3.10, 0), parent=roof_p, mat=MAT_IRON)
flag_main_p = empty("flag_main_p", (0, 3.10, 0), parent=roof_p)
flag_main = beveled_cube("flag_main", (0.50, 0.30, 0.02), bevel_offset=0.02, bevel_segments=2, loc=(0.25, 0.10, 0), parent=flag_main_p, mat=MAT_FLAG)

MAIN_TOWER_TOP = cur_y

# --- main clock face (large, centered on top stage front) ------------------
clock_p = empty("clock_p", (-3.5, MAIN_TOWER_TOP - 2.5, 1.05))
# face (large round)
face_back = smooth_torus("face_ring", r1=1.0, r2=0.10, major_segs=36, minor_segs=10, loc=(0, 0, 0.05), parent=clock_p, mat=MAT_COPPER)
face_back.rotation_euler = (0, 0, 0)
# inner face disc (cone flatten cap)
face_disc = smooth_cone("face_disc", r1=0.95, r2=0.95, depth=0.08, segs=36, loc=(0, 0, 0), parent=clock_p, mat=MAT_CLOCK_FACE)
face_disc.rotation_euler = (math.radians(90), 0, 0)
# 12 hour numerals (small cubes around)
for n in range(12):
    na = -math.pi / 2 + n * (math.pi * 2 / 12)
    nx = math.cos(na) * 0.78
    ny = math.sin(na) * 0.78
    num = beveled_cube(f"numeral_{n}", (0.12, 0.18, 0.05), bevel_offset=0.02, bevel_segments=2, loc=(nx, ny, 0.08), parent=clock_p, mat=MAT_NUMERAL)
# hour hand
hour_hand_p = empty("hour_hand_p", (0, 0, 0.12), parent=clock_p)
hour_hand = beveled_cube("hour_hand", (0.10, 0.50, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.20, 0), parent=hour_hand_p, mat=MAT_CLOCK_HAND)
# minute hand
minute_hand_p = empty("minute_hand_p", (0, 0, 0.13), parent=clock_p)
minute_hand = beveled_cube("minute_hand", (0.07, 0.75, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.35, 0), parent=minute_hand_p, mat=MAT_CLOCK_HAND)
# center cap
smooth_sphere("hand_cap", r=0.10, segs=18, rings=12, loc=(0, 0, 0.16), parent=clock_p, mat=MAT_GOLD)
# sub-cadran seconds (small below center)
sub_p = empty("sub_p", (0, -0.45, 0.10), parent=clock_p)
sub_disc = smooth_cone("sub_disc", r1=0.22, r2=0.22, depth=0.05, segs=24, loc=(0, 0, 0), parent=sub_p, mat=MAT_COPPER_DARK)
sub_disc.rotation_euler = (math.radians(90), 0, 0)
second_hand_p = empty("second_hand_p", (0, 0, 0.05), parent=sub_p)
second_hand = beveled_cube("second_hand", (0.03, 0.20, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.08, 0), parent=second_hand_p, mat=MAT_GOLD)


# --- secondary tower (3 stages, shorter) -----------------------------------
sec_tower_p = empty("sec_tower", (3.5, 0, -0.5))
SEC_HEIGHTS = [3.0, 2.5, 2.0]
SEC_RADII = [1.2, 1.0, 0.85]
cur_y = 0
for sg, (h, r) in enumerate(zip(SEC_HEIGHTS, SEC_RADII)):
    mat = MAT_BRICK if sg % 2 == 0 else MAT_STONE
    stage = smooth_cone(f"sec_stage_{sg}", r1=r, r2=r * 0.92, depth=h, segs=14, loc=(0, cur_y + h / 2, 0), parent=sec_tower_p, mat=mat)
    band = smooth_torus(f"sec_band_{sg}", r1=r * 1.02, r2=0.06, major_segs=20, minor_segs=8, loc=(0, cur_y + h - 0.10, 0), parent=sec_tower_p, mat=MAT_COPPER)
    band.rotation_euler = (math.radians(90), 0, 0)
    cur_y += h
# secondary roof
sec_roof = smooth_cone("sec_roof", r1=0.90, r2=0.0, depth=2.0, segs=14, loc=(0, cur_y + 1.0, 0), parent=sec_tower_p, mat=MAT_ROOF)
smooth_sphere("sec_ball", r=0.15, segs=18, rings=12, loc=(0, cur_y + 2.05, 0), parent=sec_tower_p, mat=MAT_GOLD)

SEC_TOWER_TOP = cur_y

# --- bridge between 2 towers -----------------------------------------------
bridge_y = 5.0
bridge_p = empty("bridge_p", (0, bridge_y, 0))
# bridge plank
bridge = beveled_cube("bridge_plank", (5.0, 0.20, 0.85), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=bridge_p, mat=MAT_COPPER_DARK)
# bridge supports (6 cables)
for c in range(6):
    cx = -2.3 + c * 0.92
    smooth_cone(f"bridge_cable_{c}", r1=0.025, r2=0.025, depth=0.6, segs=6, loc=(cx, 0.40, 0.40), parent=bridge_p, mat=MAT_IRON)
# rails
rail_top = beveled_cube("bridge_rail_top", (5.0, 0.05, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.70, 0.40), parent=bridge_p, mat=MAT_COPPER)
rail_top2 = beveled_cube("bridge_rail_top2", (5.0, 0.05, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.70, -0.40), parent=bridge_p, mat=MAT_COPPER)


# --- 8 engrenages (gears) exposed on/around towers ------------------------
gears = []
GEAR_CONFIGS = [
    # (cx, cy, cz, radius, teeth, speed, axis_rotate('Z'/'X'/'Y'))
    (-3.5, 7.5, 1.2, 0.60, 12, 0.6, 'Z'),
    (-3.5, 6.5, 1.25, 0.45, 10, -0.9, 'Z'),
    (-2.6, 7.0, 1.2, 0.35, 8, 1.2, 'Z'),
    (-4.4, 7.0, 1.2, 0.40, 9, -1.1, 'Z'),
    (3.5, 5.5, 0.95, 0.50, 11, 0.7, 'Z'),
    (3.5, 4.5, 0.95, 0.35, 8, -1.0, 'Z'),
    (4.3, 5.0, 0.95, 0.32, 7, 0.85, 'Z'),
    (0, 5.4, 0.50, 0.55, 12, 0.45, 'Z'),
]
for gi, (gx, gy, gz, gr, teeth, gspd, axis) in enumerate(GEAR_CONFIGS):
    gp = empty(f"gear_p_{gi}", (gx, gy, gz))
    # gear body (cylinder)
    body = smooth_cone(f"gear_body_{gi}", r1=gr, r2=gr, depth=0.12, segs=22, loc=(0, 0, 0), parent=gp, mat=MAT_COPPER)
    body.rotation_euler = (math.radians(90), 0, 0)
    # teeth (small cubes around)
    for tk in range(teeth):
        ta = tk * (math.pi * 2 / teeth)
        tx = math.cos(ta) * (gr + 0.06)
        ty = math.sin(ta) * (gr + 0.06)
        tooth = beveled_cube(f"gear_{gi}_tooth_{tk}", (0.08, 0.10, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(tx, ty, 0), parent=gp, mat=MAT_COPPER_DARK)
        tooth.rotation_euler = (0, 0, ta)
    # center pin
    smooth_sphere(f"gear_{gi}_pin", r=0.08, segs=14, rings=10, loc=(0, 0, 0), parent=gp, mat=MAT_GOLD)
    gears.append({"p": gp, "spd": gspd, "axis": axis})


# --- 4 chimneys with steam -------------------------------------------------
chimneys = []
CHIM_CONFIGS = [(-2.5, MAIN_TOWER_TOP, 0.8), (-4.5, MAIN_TOWER_TOP, 0.8), (4.0, SEC_TOWER_TOP, -0.5), (3.0, SEC_TOWER_TOP, -0.5)]
for ci, (cx, cy, cz) in enumerate(CHIM_CONFIGS):
    chp = empty(f"chim_p_{ci}", (cx, cy, cz))
    # chimney body
    smooth_cone(f"chim_{ci}_body", r1=0.18, r2=0.16, depth=1.2, segs=10, loc=(0, 0.60, 0), parent=chp, mat=MAT_IRON)
    # rim
    smooth_torus(f"chim_{ci}_rim", r1=0.20, r2=0.04, major_segs=14, minor_segs=8, loc=(0, 1.20, 0), parent=chp, mat=MAT_COPPER)
    # steam puffs (3 per chimney, will animate Y rise)
    steam_puffs = []
    for sp in range(3):
        puff = smooth_sphere(f"chim_{ci}_steam_{sp}", r=0.30, segs=14, rings=10, loc=(0, 1.5 + sp * 0.6, 0), parent=chp, mat=MAT_STEAM, scale=(1.2, 1.0, 1.2))
        puff["_phase"] = sp * 0.33
        steam_puffs.append(puff)
    chimneys.append({"p": chp, "puffs": steam_puffs, "idx": ci})


# --- 6 copper pipes interconnecting ---------------------------------------
pipe_configs = [
    (-3.5, 3.0, 1.0, 1.5, 0.0),    # vertical
    (-3.5, 5.0, 1.0, 2.0, 90),
    (3.5, 4.0, 0.7, 1.5, 0.0),
    (0, 3.0, 0.3, 5.0, 90),       # horizontal between towers
    (-2.0, 2.5, 0.8, 1.2, 45),
    (2.5, 2.0, 0.5, 1.0, -45),
]
for pi, (px, py, pz, plen, prot) in enumerate(pipe_configs):
    pipe = smooth_cone(f"pipe_{pi}", r1=0.10, r2=0.10, depth=plen, segs=10, loc=(px, py, pz), mat=MAT_COPPER)
    pipe.rotation_euler = (0, 0, math.radians(prot))
    # joint
    smooth_sphere(f"pipe_{pi}_joint", r=0.13, segs=14, rings=10, loc=(px, py, pz), mat=MAT_COPPER_DARK)


# --- 12 edison bulbs émissifs ---------------------------------------------
bulbs = []
BULB_POSITIONS = [
    (-3.5, 8.5, 1.0), (-3.5, 8.5, -1.0), (-2.0, 9.5, 0.3), (-5.0, 9.5, 0.3),
    (3.5, 7.0, 0.5), (3.5, 7.0, -0.5), (2.5, 7.8, -0.5), (4.5, 7.8, -0.5),
    (0, 5.5, 0.8), (0, 5.5, -0.8), (-1.5, 5.7, 0), (1.5, 5.7, 0),
]
for bi, (bx, by, bz) in enumerate(BULB_POSITIONS):
    bp = empty(f"bulb_p_{bi}", (bx, by, bz))
    # glass envelope
    glass = smooth_sphere(f"bulb_{bi}_glass", r=0.18, segs=18, rings=14, loc=(0, 0, 0), parent=bp, mat=MAT_BULB_GLASS, scale=(1.0, 1.3, 1.0))
    # filament glow
    filament = smooth_sphere(f"bulb_{bi}_fil", r=0.06, segs=12, rings=8, loc=(0, 0, 0), parent=bp, mat=MAT_EDISON)
    # socket
    smooth_cone(f"bulb_{bi}_socket", r1=0.10, r2=0.09, depth=0.10, segs=10, loc=(0, -0.20, 0), parent=bp, mat=MAT_COPPER_DARK)
    bp["_phase"] = bi * 0.27
    bulbs.append({"p": bp, "fil": filament, "phase": bi * 0.27})


# --- dirigeable amarré ----------------------------------------------------
dir_p = empty("dirigible_p", (-9, 8.5, 2.5))
# main envelope (ovoid)
smooth_sphere("dir_envelope", r=1.0, segs=24, rings=16, loc=(0, 0, 0), parent=dir_p, mat=MAT_DIRIGIBLE, scale=(2.2, 0.85, 0.85))
# trim bands (3 rings)
for tb in range(3):
    tbx = -0.9 + tb * 0.9
    band = smooth_torus(f"dir_band_{tb}", r1=0.86, r2=0.04, major_segs=22, minor_segs=8, loc=(tbx, 0, 0), parent=dir_p, mat=MAT_DIRIGIBLE_TRIM)
    band.rotation_euler = (0, math.radians(90), 0)
# gondola
gondola = beveled_cube("dir_gondola", (1.0, 0.35, 0.40), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.85, 0), parent=dir_p, mat=MAT_COPPER)
# propeller back
prop_p = empty("dir_prop_p", (-1.7, 0, 0), parent=dir_p)
for pb in range(3):
    blade = beveled_cube(f"dir_prop_b_{pb}", (0.04, 0.45, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.20, 0), parent=prop_p, mat=MAT_COPPER_DARK)
    blade.rotation_euler = (0, math.radians(120 * pb), 0)
# mooring rope (cone elongated)
rope = smooth_cone("dir_rope", r1=0.02, r2=0.02, depth=2.5, segs=6, loc=(1.0, -1.5, 0), parent=dir_p, mat=MAT_IRON)
rope.rotation_euler = (0, 0, math.radians(60))


# --- 4 drapeaux flottants -------------------------------------------------
flags = []
FLAG_POSITIONS = [(-5.0, SEC_TOWER_TOP + 1.5, 0), (-2.0, SEC_TOWER_TOP + 1.5, 0), (3.0, SEC_TOWER_TOP + 1.5, 0), (5.0, SEC_TOWER_TOP + 1.5, 0)]
for fi, (fx, fy, fz) in enumerate(FLAG_POSITIONS):
    fp = empty(f"flag_p_{fi}", (fx, fy, fz))
    # pole
    smooth_cone(f"flag_{fi}_pole", r1=0.03, r2=0.03, depth=0.8, segs=8, loc=(0, 0, 0), parent=fp, mat=MAT_IRON)
    # flag (3 segments for wave)
    flag_p_inner = empty(f"flag_{fi}_inner", (0.10, 0.30, 0), parent=fp)
    for fs in range(3):
        seg = beveled_cube(f"flag_{fi}_seg_{fs}", (0.18, 0.22, 0.015), bevel_offset=0.01, bevel_segments=2, loc=(0.18 * fs + 0.10, 0, 0), parent=flag_p_inner, mat=MAT_FLAG)
    flags.append({"p": fp, "inner": flag_p_inner, "phase": fi * 0.5})


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

    # --- 8 gears rotate
    for gd in gears:
        ang = tt * 2 * math.pi * gd["spd"] * 2
        kf(gd["p"], f, "rotation_euler", (math.radians(90), 0, ang))

    # --- 3 clock hands rotate
    # hour : 1 cycle per 6 sec (full hour cycle)
    hour_ang = tt * 2 * math.pi * 1.0
    minute_ang = tt * 2 * math.pi * 12.0  # 12 cycles per duration (12x faster)
    second_ang = tt * 2 * math.pi * 60.0  # 60 cycles
    kf(hour_hand_p, f, "rotation_euler", (0, 0, -hour_ang))
    kf(minute_hand_p, f, "rotation_euler", (0, 0, -minute_ang))
    kf(second_hand_p, f, "rotation_euler", (0, 0, -second_ang))

    # --- 4 chimneys : steam rise
    for ch in chimneys:
        for sp_i, puff in enumerate(ch["puffs"]):
            ph = puff["_phase"]
            local = (tt * 1.5 + ph) % 1.0
            ny = 1.5 + local * 3.5
            sc = 1.0 + local * 1.5
            kf(puff, f, "location", (0, ny, 0))
            kf(puff, f, "scale", (sc, sc, sc))

    # --- 12 bulbs pulse différentielles (scale + can't animate emi directly, scale fil)
    for bd in bulbs:
        ph = bd["phase"]
        pulse = 1.0 + 0.20 * math.sin(2 * math.pi * tt * 3.5 + ph * math.pi)
        kf(bd["fil"], f, "scale", (pulse, pulse, pulse))

    # --- dirigible bob + sway
    dx = -9 + 0.5 * math.sin(2 * math.pi * tt * 0.6)
    dy = 8.5 + 0.35 * math.cos(2 * math.pi * tt * 0.8)
    dz = 2.5 + 0.4 * math.sin(2 * math.pi * tt * 0.7)
    kf(dir_p, f, "location", (dx, dy, dz))
    kf(dir_p, f, "rotation_euler", (math.radians(3 * math.sin(2 * math.pi * tt * 1.2)), math.radians(5 * math.sin(2 * math.pi * tt * 0.5)), math.radians(2 * math.sin(2 * math.pi * tt * 1.0))))
    # propeller spin
    kf(prop_p, f, "rotation_euler", (math.radians(360 * tt * 10), 0, 0))

    # --- 4 flags flutter
    for fd in flags:
        ph = fd["phase"]
        wave = math.radians(20) * math.sin(2 * math.pi * tt * 3.5 + ph * math.pi)
        kf(fd["inner"], f, "rotation_euler", (0, wave, math.radians(8 * math.cos(2 * math.pi * tt * 3.0 + ph * math.pi))))

    # also main tower flag
    main_flag_wave = math.radians(25) * math.sin(2 * math.pi * tt * 3.5)
    kf(flag_main_p, f, "rotation_euler", (0, main_flag_wave, math.radians(10 * math.cos(2 * math.pi * tt * 3.0))))

    # --- 3 clouds drift
    for clk, cp in enumerate(clouds):
        bx_ = cp["_base_x"]
        spd = cp["_speed"]
        new_x = bx_ + tt * spd * 4 - 2
        if new_x > 15:
            new_x -= 30
        kf(cp, f, "location", (new_x, cp.location.y if f > 1 else cp.location.y, cp.location.z))

    # --- sun pulse + halos breathe
    sun_p_pulse = 1.0 + 0.04 * math.sin(2 * math.pi * tt * 2)
    kf(sun, f, "scale", (sun_p_pulse, sun_p_pulse, sun_p_pulse))
    for hi, halo in enumerate([sun_halo_1, sun_halo_2]):
        breath = 1.0 + 0.10 * math.sin(2 * math.pi * tt * (1.5 - hi * 0.3) + hi * 1.2)
        kf(halo, f, "scale", (breath, breath, breath))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_steampunk_clock_tower] wrote {OUT}")
