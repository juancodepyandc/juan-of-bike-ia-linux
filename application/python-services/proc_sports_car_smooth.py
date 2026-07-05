"""
proc_sports_car_smooth.py — 137e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Voiture de sport rouge type Lamborghini avec :
- Carrosserie smooth shaded + bevels + subdivisions (formes lisses)
- 4 roues détaillées avec jantes alliage (6 spokes chacune)
- Spoiler arrière
- Phares LED émissifs avec halos
- Feux arrière émissifs rouge
- 2 portes en élytre (animations s'ouvrent et ferment)
- Cockpit visible à travers windshield translucide
- Sol garage damier émissif
- 4 lampes plafond pulse
- Miroir réfléchissant
- Underglow cyan

Animations multi-axes :
- 4 roues : rotation X rapide
- 2 portes élytre : rotation Z s'ouvrent puis ferment cycliquement
- spoiler : tilt X dynamique
- phares + feux : pulse émission
- voiture : subtle bob + slight rotation continuous
- 4 lampes plafond : pulse phases offset
- underglow : pulse continuous

Sortie : output/3d/pbr_sportscar_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_sportscar_proc.glb"))

random.seed(0xC0FFEE)

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
    """Apply smooth shading on polygons (Blender 4.2+ compatibility)."""
    for poly in mesh.polygons:
        poly.use_smooth = True
    # Blender 4.2 removed use_auto_smooth ; rely on smooth polygons + edge sharpness when needed
    try:
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40)
    except AttributeError:
        pass


def beveled_cube(name, size_xyz, bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=None, mat=None, smooth=True):
    """Build a beveled cube — much smoother than a raw cube."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    # scale uniformly first
    bmesh.ops.scale(bm, vec=(size_xyz[0], size_xyz[1], size_xyz[2]), verts=bm.verts)
    # bevel all edges
    bmesh.ops.bevel(
        bm,
        geom=bm.edges[:] + bm.verts[:],
        offset=bevel_offset,
        segments=bevel_segments,
        profile=0.5,
        affect='EDGES',
    )
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    if smooth:
        smooth_shade(me)
    return o


def smooth_sphere(name, r=1.0, segs=32, rings=20, loc=(0, 0, 0), parent=None, mat=None):
    """High-poly smooth-shaded sphere."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


def smooth_cone(name, r1=1.0, r2=0.0, depth=1.0, segs=24, loc=(0, 0, 0), parent=None, mat=None):
    """High-poly smooth-shaded cone."""
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


def stretched_smooth_sphere(name, r=1.0, segs=32, rings=20, scale=(1, 1, 1), loc=(0, 0, 0), parent=None, mat=None, subdivide=0):
    """Smooth-shaded UV sphere with applied non-uniform scale to verts (so smoothing reads the deformed shape)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    if subdivide > 0:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=subdivide, use_grid_fill=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = loc
    if mat:
        me.materials.append(mat)
    smooth_shade(me)
    return o


# --- materials --------------------------------------------------------------
MAT_GARAGE_WALL = make_mat("garage_wall", (0.15, 0.15, 0.18), roughness=0.5,
                             emi=(0.05, 0.05, 0.08), emi_strength=0.2)
MAT_FLOOR_DARK = make_mat("floor_dark", (0.05, 0.05, 0.06), metallic=0.6, roughness=0.05)
MAT_FLOOR_CHECK = make_mat("floor_check", (0.90, 0.90, 0.92), roughness=0.2,
                             emi=(0.30, 0.30, 0.35), emi_strength=0.6)
MAT_CAR_BODY = make_mat("car_body", (0.85, 0.05, 0.05), metallic=0.95, roughness=0.15,
                          emi=(0.20, 0.02, 0.02), emi_strength=0.3)
MAT_CAR_BODY_DARK = make_mat("car_body_dark", (0.40, 0.03, 0.03), metallic=0.9, roughness=0.20)
MAT_WINDSHIELD = make_mat("windshield", (0.10, 0.15, 0.20), roughness=0.0, alpha=0.45, metallic=0.5,
                            emi=(0.05, 0.10, 0.18), emi_strength=0.4)
MAT_INTERIOR = make_mat("interior", (0.20, 0.18, 0.15), roughness=0.7,
                          emi=(0.10, 0.08, 0.05), emi_strength=0.3)
MAT_SEAT_RED = make_mat("seat_red", (0.55, 0.10, 0.10), roughness=0.5,
                          emi=(0.20, 0.05, 0.05), emi_strength=0.3)
MAT_TIRE = make_mat("tire", (0.05, 0.05, 0.05), roughness=0.8)
MAT_RIM = make_mat("rim", (0.85, 0.85, 0.92), metallic=0.95, roughness=0.15,
                     emi=(0.25, 0.25, 0.30), emi_strength=0.3)
MAT_RIM_DARK = make_mat("rim_dark", (0.30, 0.30, 0.35), metallic=0.85, roughness=0.3)
MAT_HEADLIGHT = make_mat("headlight", (1.0, 0.98, 0.85), roughness=0.0,
                           emi=(1.0, 0.98, 0.85), emi_strength=12.0)
MAT_HEADLIGHT_HALO = make_mat("hl_halo", (1.0, 0.98, 0.85), roughness=0.0, alpha=0.30,
                                emi=(1.0, 0.95, 0.80), emi_strength=4.0)
MAT_TAILLIGHT = make_mat("taillight", (1.0, 0.10, 0.10), roughness=0.0,
                           emi=(1.0, 0.10, 0.10), emi_strength=8.0)
MAT_UNDERGLOW = make_mat("underglow", (0.20, 0.85, 1.0), roughness=0.0, alpha=0.65,
                           emi=(0.20, 0.85, 1.0), emi_strength=6.0)
MAT_SPOILER = make_mat("spoiler", (0.10, 0.10, 0.10), metallic=0.7, roughness=0.30)
MAT_CHROME = make_mat("chrome", (0.92, 0.92, 0.95), metallic=0.98, roughness=0.05)
MAT_GRILLE = make_mat("grille", (0.05, 0.05, 0.05), metallic=0.6, roughness=0.4)
MAT_LICENSE = make_mat("license", (0.95, 0.92, 0.85), roughness=0.4,
                         emi=(0.40, 0.38, 0.32), emi_strength=0.4)
MAT_LAMP_LIGHT = make_mat("lamp_light", (1.0, 0.92, 0.75), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.92, 0.75), emi_strength=9.0)
MAT_LAMP_CASE = make_mat("lamp_case", (0.25, 0.25, 0.25), metallic=0.6, roughness=0.4)
MAT_MIRROR = make_mat("mirror", (0.95, 0.95, 0.98), metallic=0.99, roughness=0.02,
                        emi=(0.30, 0.30, 0.35), emi_strength=0.3)
MAT_EXHAUST = make_mat("exhaust", (0.55, 0.55, 0.60), metallic=0.85, roughness=0.25,
                         emi=(0.10, 0.10, 0.12), emi_strength=0.3)

# --- garage room (3 walls + ceiling + floor) -------------------------------
# floor (checkerboard)
N_CHECK = 8
CELL = 1.5
for i in range(N_CHECK):
    for j in range(N_CHECK):
        x = -N_CHECK * CELL / 2 + i * CELL + CELL / 2
        z = -N_CHECK * CELL / 2 + j * CELL + CELL / 2
        mat = MAT_FLOOR_CHECK if (i + j) % 2 == 0 else MAT_FLOOR_DARK
        tile = beveled_cube(f"floor_{i}_{j}", (CELL * 0.48, 0.04, CELL * 0.48), bevel_offset=0.02, bevel_segments=2, loc=(x, 0, z), mat=mat)
floor_base = beveled_cube("floor_base", (16, 0.05, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.04, 0), mat=MAT_FLOOR_DARK)

# back wall
back_wall = beveled_cube("back_wall", (16, 6, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 3, -7.5), mat=MAT_GARAGE_WALL)
# left + right walls
for side, dx in [("L", -8), ("R", 8)]:
    w = beveled_cube(f"wall_{side}", (0.3, 6, 16), bevel_offset=0.05, bevel_segments=2, loc=(dx, 3, 0), mat=MAT_GARAGE_WALL)
# ceiling
ceiling = beveled_cube("ceiling", (16, 0.3, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 6, 0), mat=MAT_GARAGE_WALL)

# --- the sports car body -----------------------------------------------------
car = empty("car", (0, 0.5, 0))

# main chassis (low, wide, beveled smooth) — using subdivided cube for smoothness
def make_chassis(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(4.0, 0.5, 1.6), verts=bm.verts)
    # bevel heavily
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=0.18, segments=5, profile=0.7, affect='EDGES')
    # subdivide for smoother shape
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0, 0.30, 0)
    me.materials.append(MAT_CAR_BODY)
    smooth_shade(me)
    return o

chassis = make_chassis("chassis", car)

# front hood (sloped, smoothed)
hood = beveled_cube("hood", (1.4, 0.10, 1.55), bevel_offset=0.12, bevel_segments=4, loc=(1.3, 0.50, 0), parent=car, mat=MAT_CAR_BODY)
hood.rotation_euler = (0, 0, math.radians(-5))

# rear hood
rear_hood = beveled_cube("rear_hood", (1.4, 0.10, 1.55), bevel_offset=0.12, bevel_segments=4, loc=(-1.3, 0.50, 0), parent=car, mat=MAT_CAR_BODY)
rear_hood.rotation_euler = (0, 0, math.radians(5))

# roof / cockpit dome (curved windshield piece)
roof_p = empty("roof_p", (0, 0.65, 0), parent=car)
# windshield (translucent, slanted)
windshield = beveled_cube("windshield", (0.8, 0.05, 1.45), bevel_offset=0.08, bevel_segments=3, loc=(0.3, 0.5, 0), parent=roof_p, mat=MAT_WINDSHIELD)
windshield.rotation_euler = (0, 0, math.radians(-35))
# rear windshield
rear_windshield = beveled_cube("rear_windshield", (0.7, 0.05, 1.45), bevel_offset=0.08, bevel_segments=3, loc=(-0.4, 0.5, 0), parent=roof_p, mat=MAT_WINDSHIELD)
rear_windshield.rotation_euler = (0, 0, math.radians(30))
# roof panel between windshields
roof = beveled_cube("roof", (0.6, 0.10, 1.40), bevel_offset=0.08, bevel_segments=3, loc=(0, 0.70, 0), parent=car, mat=MAT_CAR_BODY_DARK)

# 2 doors (élytre style - hinge at top of side, open upward)
doors = []
for side, dz in [("L", 0.78), ("R", -0.78)]:
    door_p = empty(f"door_p_{side}", (0, 0.45, dz), parent=car)
    door = beveled_cube(f"door_{side}", (1.6, 0.08, 0.10), bevel_offset=0.08, bevel_segments=3, loc=(0, 0, 0), parent=door_p, mat=MAT_CAR_BODY)
    # door window (semi-translucent)
    door_win = beveled_cube(f"door_win_{side}", (1.4, 0.04, 0.05), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.25, 0), parent=door_p, mat=MAT_WINDSHIELD)
    # door handle
    handle = smooth_cone(f"door_handle_{side}", r1=0.04, r2=0.04, depth=0.10, segs=12, loc=(0, 0, 0.08 if side == "L" else -0.08), parent=door_p, mat=MAT_CHROME)
    handle.rotation_euler = (math.radians(90), 0, 0)
    doors.append(door_p)

# --- 4 wheels with detailed rims ------------------------------------------
def make_wheel(name, x, z, parent):
    p = empty(name, (x, 0.40, z), parent=parent)
    # tire (smooth shaded)
    tire = smooth_cone(f"{name}_tire", r1=0.45, r2=0.45, depth=0.30, segs=32, loc=(0, 0, 0), parent=p, mat=MAT_TIRE)
    tire.rotation_euler = (0, math.radians(90), 0)
    # tire side bevel detail (inner ring)
    inner_ring = smooth_cone(f"{name}_inner", r1=0.43, r2=0.43, depth=0.32, segs=24, loc=(0, 0, 0), parent=p, mat=MAT_TIRE)
    inner_ring.rotation_euler = (0, math.radians(90), 0)
    inner_ring.scale = (0.95, 1.0, 0.95)
    # rim disc (alloy)
    rim = smooth_cone(f"{name}_rim", r1=0.32, r2=0.32, depth=0.06, segs=24, loc=(0, 0, 0.16), parent=p, mat=MAT_RIM)
    rim.rotation_euler = (0, math.radians(90), 0)
    # 6 spokes (alloy detail)
    for k in range(6):
        ka = k * (math.pi / 3)
        spoke = beveled_cube(f"{name}_spoke_{k}", (0.04, 0.03, 0.28), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0.16), parent=p, mat=MAT_RIM)
        spoke.rotation_euler = (ka, 0, 0)
    # center cap
    cap = smooth_sphere(f"{name}_cap", r=0.10, segs=16, rings=12, loc=(0, 0, 0.20), parent=p, mat=MAT_RIM_DARK)
    return p

wheels = []
wheel_data = [(1.5, 0.85), (1.5, -0.85), (-1.5, 0.85), (-1.5, -0.85)]
for i, (wx, wz) in enumerate(wheel_data):
    w = make_wheel(f"wheel_{i}", wx, wz, car)
    wheels.append(w)

# --- spoiler (rear wing, animated tilt) ----------------------------------
spoiler_p = empty("spoiler_p", (-1.85, 0.85, 0), parent=car)
# 2 vertical mounts
for side, dz in [("L", 0.55), ("R", -0.55)]:
    mount = beveled_cube(f"spoiler_mount_{side}", (0.06, 0.30, 0.06), bevel_offset=0.01, bevel_segments=2, loc=(0, -0.15, dz), parent=spoiler_p, mat=MAT_SPOILER)
# main wing
wing = beveled_cube("spoiler_wing", (0.4, 0.06, 1.4), bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=spoiler_p, mat=MAT_SPOILER)

# --- headlights with halos -----------------------------------------------
headlights = []
for side, dz in [("L", 0.50), ("R", -0.50)]:
    hl_p = empty(f"hl_p_{side}", (2.0, 0.50, dz), parent=car)
    hl = smooth_sphere(f"hl_{side}", r=0.16, segs=20, rings=14, loc=(0, 0, 0), parent=hl_p, mat=MAT_HEADLIGHT)
    hl.scale = (0.6, 0.9, 0.9)
    # halo (larger translucent sphere)
    halo = smooth_sphere(f"hl_halo_{side}", r=0.28, segs=18, rings=12, loc=(0, 0, 0), parent=hl_p, mat=MAT_HEADLIGHT_HALO)
    halo.scale = (0.5, 1.0, 1.0)
    # LED strip (3 small spheres)
    for k in range(3):
        led = smooth_sphere(f"hl_led_{side}_{k}", r=0.03, segs=10, rings=8, loc=(0.13, -0.05 + k * 0.05, 0), parent=hl_p, mat=MAT_HEADLIGHT)
    headlights.append(hl)

# grille (front)
grille = beveled_cube("grille", (0.10, 0.20, 1.0), bevel_offset=0.03, bevel_segments=3, loc=(2.10, 0.30, 0), parent=car, mat=MAT_GRILLE)
# grille bars
for k in range(7):
    bar = beveled_cube(f"grille_bar_{k}", (0.04, 0.04, 0.95), bevel_offset=0.01, bevel_segments=2, loc=(2.13, 0.25 - k * 0.025, 0), parent=car, mat=MAT_CHROME)

# --- taillights ------------------------------------------------------------
taillights = []
for side, dz in [("L", 0.55), ("R", -0.55)]:
    tl_p = empty(f"tl_p_{side}", (-2.0, 0.50, dz), parent=car)
    tl = beveled_cube(f"tl_{side}", (0.06, 0.15, 0.35), bevel_offset=0.03, bevel_segments=3, loc=(0, 0, 0), parent=tl_p, mat=MAT_TAILLIGHT)
    # 3 internal LED accents (stretched)
    for k in range(3):
        led = beveled_cube(f"tl_led_{side}_{k}", (0.04, 0.03, 0.30), bevel_offset=0.01, bevel_segments=2, loc=(-0.03, -0.05 + k * 0.05, 0), parent=tl_p, mat=MAT_TAILLIGHT)
    taillights.append(tl)

# license plate
license_plate = beveled_cube("license", (0.05, 0.10, 0.35), bevel_offset=0.02, bevel_segments=2, loc=(-2.08, 0.20, 0), parent=car, mat=MAT_LICENSE)

# 2 exhaust pipes
for side, dz in [("L", 0.25), ("R", -0.25)]:
    exh = smooth_cone(f"exhaust_{side}", r1=0.07, r2=0.08, depth=0.20, segs=16, loc=(-2.05, 0.20, dz), parent=car, mat=MAT_EXHAUST)
    exh.rotation_euler = (0, math.radians(90), 0)

# 2 side mirrors
for side, dz in [("L", 0.92), ("R", -0.92)]:
    mr_p = empty(f"mirror_p_{side}", (0.5, 0.65, dz), parent=car)
    arm = beveled_cube(f"mirror_arm_{side}", (0.06, 0.04, 0.12), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0), parent=mr_p, mat=MAT_CAR_BODY)
    glass = beveled_cube(f"mirror_glass_{side}", (0.04, 0.10, 0.14), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.10), parent=mr_p, mat=MAT_MIRROR)

# --- underglow strip beneath car ------------------------------------------
underglow = beveled_cube("underglow_strip", (3.6, 0.04, 1.4), bevel_offset=0.05, bevel_segments=3, loc=(0, 0.10, 0), parent=car, mat=MAT_UNDERGLOW)

# --- interior (visible through windshield) -------------------------------
# 2 seats (visible from above)
for side, dz in [("L", 0.40), ("R", -0.40)]:
    # seat base
    seat_base = beveled_cube(f"seat_base_{side}", (0.50, 0.08, 0.40), bevel_offset=0.05, bevel_segments=3, loc=(0.10, 0.45, dz), parent=car, mat=MAT_SEAT_RED)
    # seat back
    seat_back = beveled_cube(f"seat_back_{side}", (0.10, 0.55, 0.40), bevel_offset=0.05, bevel_segments=3, loc=(-0.20, 0.65, dz), parent=car, mat=MAT_SEAT_RED)
# steering wheel
sw_p = empty("steering_wheel", (0.6, 0.65, 0.40), parent=car)
sw_p.rotation_euler = (0, 0, math.radians(-20))
sw_ring = smooth_cone("sw_ring", r1=0.18, r2=0.18, depth=0.04, segs=20, loc=(0, 0, 0), parent=sw_p, mat=MAT_INTERIOR)
sw_ring.rotation_euler = (0, math.radians(90), 0)
# 3 spokes
for k in range(3):
    ka = k * (math.pi * 2 / 3)
    sp = beveled_cube(f"sw_sp_{k}", (0.03, 0.16, 0.03), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0), parent=sw_p, mat=MAT_INTERIOR)
    sp.rotation_euler = (ka, 0, 0)
# dashboard
dash = beveled_cube("dash", (0.6, 0.10, 0.90), bevel_offset=0.04, bevel_segments=2, loc=(0.85, 0.55, 0), parent=car, mat=MAT_INTERIOR)

# --- 4 lampes plafond garage ---------------------------------------------
ceiling_lamps = []
for i, (lx, lz) in enumerate([(-4, 4), (4, 4), (-4, -4), (4, -4)]):
    lp = empty(f"clamp_{i}", (lx, 5.8, lz))
    # rod
    rod = smooth_cone(f"clamp_{i}_rod", r1=0.04, r2=0.04, depth=0.40, segs=10, loc=(0, -0.20, 0), parent=lp, mat=MAT_LAMP_CASE)
    rod.rotation_euler = (math.radians(90), 0, 0)
    # shade
    shade = smooth_cone(f"clamp_{i}_shade", r1=0.30, r2=0.18, depth=0.25, segs=20, loc=(0, -0.45, 0), parent=lp, mat=MAT_LAMP_CASE)
    shade.rotation_euler = (math.radians(180), 0, 0)
    # bulb
    bulb = smooth_sphere(f"clamp_{i}_bulb", r=0.18, segs=20, rings=14, loc=(0, -0.55, 0), parent=lp, mat=MAT_LAMP_LIGHT)
    ceiling_lamps.append(bulb)

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

# 4 wheels rotate (fast)
for i, w in enumerate(wheels):
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        kf_rot(w, f, (tt * math.pi * 16, 0, 0))  # 8 turns/loop

# car gentle bob + slight rotation Z
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    by = 0.5 + 0.05 * math.sin(tt * math.pi * 4.0)
    tilt = math.radians(2) * math.sin(tt * math.pi * 3.0)
    kf_loc(car, f, (0, by, 0))
    kf_rot(car, f, (0, math.radians(15) * math.sin(tt * math.pi * 2.0), tilt))

# 2 doors open + close (élytre rotation)
for i, door_p in enumerate(doors):
    base_x = door_p.location.x
    base_y = door_p.location.y
    base_z = door_p.location.z
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        # 2 cycles of open/close
        local = (tt * 2.0) % 1.0
        # open from 0 to 0.5, close from 0.5 to 1.0
        if local < 0.5:
            angle = local * 2.0 * math.radians(60)
        else:
            angle = (1.0 - local) * 2.0 * math.radians(60)
        # rotation Y opens upward (élytre)
        sign = 1 if i == 0 else -1
        kf_rot(door_p, f, (0, 0, angle * sign))

# spoiler tilts dynamically (suggests aerodynamics)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    tilt = math.radians(8) * math.sin(tt * math.pi * 3.0)
    kf_rot(spoiler_p, f, (tilt, 0, 0))

# headlights pulse
for hl in headlights:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 6.0)
        kf_scale(hl, f, (0.6 * s, 0.9 * s, 0.9 * s))

# taillights pulse (brake light style)
for tl in taillights:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.20 * math.sin(tt * math.pi * 5.0)
        kf_scale(tl, f, (s, s, s))

# 4 ceiling lamps pulse
for i, bulb in enumerate(ceiling_lamps):
    phase = i * 0.4
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(bulb, f, (s, s, s))

# underglow pulse
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.25 * math.sin(tt * math.pi * 7.0)
    kf_scale(underglow, f, (3.6 * s, 0.04, 1.4 * s))

# steering wheel rotates (driver turning)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = math.radians(30) * math.sin(tt * math.pi * 2.5)
    kf_rot(sw_p, f, (angle, 0, math.radians(-20)))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_sportscar] wrote {OUT}")
