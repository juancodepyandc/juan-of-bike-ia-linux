"""
proc_motorcycle_chopper.py — 138e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth shading + bevels + multi-axis anim).

Moto chopper Harley smooth-shaded :
- Réservoir bombé bevelé + smooth
- 2 roues énormes avec tires segs=32 + rims chromés smooth + 6 spokes alliage
+ jantes alliage smooth + center caps
- Selle cuir bevelé courbée
- Guidon courbe (cubes bevelés + chrome handles)
- 2 pots échappement chrome cylindriques longs
- Phare avant émissif intense + halo
- 2 miroirs miroirs smooth réfléchissants
- Cadre tube smooth avec multiples segments cylindriques chromés
- 2 fourches avant smooth
- Pédales + repose-pieds
- 2 clignotants émissifs orange alternance
- Plaque immatriculation
- Sol garage damier 64 tiles
- 4 lampes plafond pulse
- Mur background

Animations multi-axes :
- 2 roues : rotation X rapide (12 turns/loop)
- moteur subtle scale vibration (haute fréquence)
- guidon : rotate Z léger ±15° (driver tourne)
- phare avant : pulse intense
- 2 clignotants : ON/OFF alternance scale
- 4 lampes : pulse phases offset
- chopper subtle bob + tilt

Sortie : output/3d/pbr_chopper_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_chopper_proc.glb"))

random.seed(0xCAFE17)

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
    """Apply smooth shading on polygons (Blender 4.2+ compatible)."""
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
MAT_GARAGE_WALL = make_mat("garage_wall", (0.18, 0.18, 0.22), roughness=0.5,
                             emi=(0.06, 0.06, 0.10), emi_strength=0.2)
MAT_FLOOR_DARK = make_mat("floor_dark", (0.05, 0.05, 0.08), metallic=0.6, roughness=0.05)
MAT_FLOOR_CHECK = make_mat("floor_check", (0.85, 0.85, 0.88), roughness=0.2,
                             emi=(0.30, 0.30, 0.32), emi_strength=0.6)
MAT_TANK = make_mat("tank", (0.65, 0.10, 0.05), metallic=0.95, roughness=0.15,
                      emi=(0.20, 0.02, 0.02), emi_strength=0.3)
MAT_TANK_STRIPE = make_mat("tank_stripe", (1.0, 0.85, 0.20), metallic=0.85, roughness=0.25,
                             emi=(0.30, 0.25, 0.05), emi_strength=0.4)
MAT_TIRE = make_mat("tire", (0.05, 0.05, 0.05), roughness=0.8)
MAT_RIM = make_mat("rim", (0.90, 0.90, 0.95), metallic=0.95, roughness=0.10,
                     emi=(0.25, 0.25, 0.30), emi_strength=0.3)
MAT_RIM_DARK = make_mat("rim_dark", (0.30, 0.30, 0.35), metallic=0.85, roughness=0.3)
MAT_CHROME = make_mat("chrome", (0.95, 0.95, 0.98), metallic=0.99, roughness=0.05)
MAT_FRAME = make_mat("frame", (0.10, 0.10, 0.10), metallic=0.7, roughness=0.30)
MAT_LEATHER = make_mat("leather", (0.20, 0.10, 0.05), roughness=0.7)
MAT_LEATHER_STITCH = make_mat("stitch", (0.85, 0.65, 0.30), roughness=0.5,
                                emi=(0.20, 0.15, 0.05), emi_strength=0.3)
MAT_HEADLIGHT = make_mat("headlight", (1.0, 0.95, 0.80), roughness=0.0,
                           emi=(1.0, 0.95, 0.80), emi_strength=14.0)
MAT_HL_HALO = make_mat("hl_halo", (1.0, 0.95, 0.80), roughness=0.0, alpha=0.30,
                         emi=(1.0, 0.92, 0.75), emi_strength=4.5)
MAT_BLINKER = make_mat("blinker", (1.0, 0.50, 0.05), roughness=0.0,
                         emi=(1.0, 0.50, 0.05), emi_strength=10.0)
MAT_ENGINE_BLACK = make_mat("engine_black", (0.08, 0.08, 0.08), metallic=0.65, roughness=0.3)
MAT_ENGINE_CHROME = make_mat("engine_chrome", (0.85, 0.85, 0.88), metallic=0.95, roughness=0.15)
MAT_EXHAUST = make_mat("exhaust", (0.85, 0.85, 0.90), metallic=0.99, roughness=0.05,
                         emi=(0.10, 0.10, 0.12), emi_strength=0.3)
MAT_LICENSE = make_mat("license", (0.95, 0.92, 0.85), roughness=0.4,
                         emi=(0.35, 0.32, 0.28), emi_strength=0.4)
MAT_MIRROR = make_mat("mirror_glass", (0.95, 0.95, 0.98), metallic=0.99, roughness=0.02,
                        emi=(0.30, 0.30, 0.35), emi_strength=0.3)
MAT_LAMP_LIGHT = make_mat("lamp_light", (1.0, 0.92, 0.70), roughness=0.0, alpha=0.85,
                            emi=(1.0, 0.92, 0.70), emi_strength=9.0)
MAT_LAMP_CASE = make_mat("lamp_case", (0.25, 0.25, 0.25), metallic=0.6, roughness=0.4)
MAT_CHAIN = make_mat("chain", (0.45, 0.45, 0.48), metallic=0.85, roughness=0.30)
MAT_FORK = make_mat("fork", (0.85, 0.85, 0.88), metallic=0.95, roughness=0.10)

# --- garage room -------------------------------------------------------
N_CHECK = 8
CELL = 1.5
for i in range(N_CHECK):
    for j in range(N_CHECK):
        x = -N_CHECK * CELL / 2 + i * CELL + CELL / 2
        z = -N_CHECK * CELL / 2 + j * CELL + CELL / 2
        mat = MAT_FLOOR_CHECK if (i + j) % 2 == 0 else MAT_FLOOR_DARK
        beveled_cube(f"floor_{i}_{j}", (CELL * 0.48, 0.04, CELL * 0.48), bevel_offset=0.02, bevel_segments=2, loc=(x, 0, z), mat=mat)
floor_base = beveled_cube("floor_base", (16, 0.05, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.04, 0), mat=MAT_FLOOR_DARK)

# back wall
back_wall = beveled_cube("back_wall", (16, 6, 0.3), bevel_offset=0.05, bevel_segments=2, loc=(0, 3, -7.5), mat=MAT_GARAGE_WALL)
# 2 side walls
for side, dx in [("L", -8), ("R", 8)]:
    w = beveled_cube(f"wall_{side}", (0.3, 6, 16), bevel_offset=0.05, bevel_segments=2, loc=(dx, 3, 0), mat=MAT_GARAGE_WALL)
# ceiling
ceiling = beveled_cube("ceiling", (16, 0.3, 16), bevel_offset=0.05, bevel_segments=2, loc=(0, 6, 0), mat=MAT_GARAGE_WALL)

# --- chopper -----------------------------------------------------------
chopper = empty("chopper", (0, 0.7, 0))

# --- front wheel (large, raked forward) ----------------------------------
front_wheel_p = empty("front_wheel", (1.5, -0.10, 0), parent=chopper)
# tire
front_tire = smooth_cone("front_tire", r1=0.55, r2=0.55, depth=0.22, segs=32, loc=(0, 0, 0), parent=front_wheel_p, mat=MAT_TIRE)
front_tire.rotation_euler = (0, math.radians(90), 0)
# rim (alloy)
front_rim = smooth_cone("front_rim", r1=0.38, r2=0.38, depth=0.05, segs=32, loc=(0, 0, 0.12), parent=front_wheel_p, mat=MAT_RIM)
front_rim.rotation_euler = (0, math.radians(90), 0)
# 6 spokes
for k in range(6):
    ka = k * (math.pi / 3)
    spoke = beveled_cube(f"front_spoke_{k}", (0.04, 0.04, 0.35), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0.12), parent=front_wheel_p, mat=MAT_RIM)
    spoke.rotation_euler = (ka, 0, 0)
# center cap
front_cap = smooth_sphere("front_cap", r=0.10, segs=20, rings=14, loc=(0, 0, 0.16), parent=front_wheel_p, mat=MAT_RIM_DARK)
# back ring
front_back = smooth_cone("front_back", r1=0.38, r2=0.38, depth=0.04, segs=32, loc=(0, 0, -0.12), parent=front_wheel_p, mat=MAT_RIM)
front_back.rotation_euler = (0, math.radians(90), 0)

# --- back wheel (even larger) -------------------------------------------
back_wheel_p = empty("back_wheel", (-1.0, -0.10, 0), parent=chopper)
back_tire = smooth_cone("back_tire", r1=0.65, r2=0.65, depth=0.28, segs=32, loc=(0, 0, 0), parent=back_wheel_p, mat=MAT_TIRE)
back_tire.rotation_euler = (0, math.radians(90), 0)
# rim
back_rim = smooth_cone("back_rim", r1=0.45, r2=0.45, depth=0.06, segs=32, loc=(0, 0, 0.15), parent=back_wheel_p, mat=MAT_RIM)
back_rim.rotation_euler = (0, math.radians(90), 0)
# 6 spokes
for k in range(6):
    ka = k * (math.pi / 3)
    spoke = beveled_cube(f"back_spoke_{k}", (0.04, 0.04, 0.42), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0.15), parent=back_wheel_p, mat=MAT_RIM)
    spoke.rotation_euler = (ka, 0, 0)
# center cap
back_cap = smooth_sphere("back_cap", r=0.12, segs=20, rings=14, loc=(0, 0, 0.20), parent=back_wheel_p, mat=MAT_RIM_DARK)
# back ring
back_back = smooth_cone("back_back", r1=0.45, r2=0.45, depth=0.05, segs=32, loc=(0, 0, -0.15), parent=back_wheel_p, mat=MAT_RIM)
back_back.rotation_euler = (0, math.radians(90), 0)

# --- frame (multi-segment tube) ----------------------------------------
# main backbone
frame_main = smooth_cone("frame_main", r1=0.06, r2=0.06, depth=2.0, segs=14, loc=(0.2, 0.5, 0), parent=chopper, mat=MAT_FRAME)
frame_main.rotation_euler = (0, math.radians(90), 0)
# 2 lower frame tubes (going to back wheel)
for side, dz in [("L", 0.10), ("R", -0.10)]:
    lower = smooth_cone(f"frame_lower_{side}", r1=0.05, r2=0.05, depth=1.4, segs=12, loc=(-0.4, 0.1, dz), parent=chopper, mat=MAT_FRAME)
    lower.rotation_euler = (0, math.radians(90), 0)
# vertical seat post
seat_post = smooth_cone("seat_post", r1=0.04, r2=0.04, depth=0.5, segs=10, loc=(-0.7, 0.35, 0), parent=chopper, mat=MAT_CHROME)
seat_post.rotation_euler = (math.radians(90), 0, 0)

# --- fuel tank (large bevelled, hump shape) -----------------------------
def make_tank(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    # start from sphere stretched for the hump shape
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=0.4)
    bmesh.ops.scale(bm, vec=(1.6, 1.0, 0.85), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (0.4, 0.65, 0)
    me.materials.append(MAT_TANK)
    smooth_shade(me)
    return o

tank = make_tank("fuel_tank", chopper)
# yellow stripe on tank (decoration)
tank_stripe = beveled_cube("tank_stripe", (1.3, 0.06, 0.05), bevel_offset=0.02, bevel_segments=2, loc=(0.4, 0.80, 0), parent=chopper, mat=MAT_TANK_STRIPE)
# tank cap
tank_cap = smooth_cone("tank_cap", r1=0.06, r2=0.06, depth=0.04, segs=14, loc=(0.4, 0.95, 0), parent=chopper, mat=MAT_CHROME)
tank_cap.rotation_euler = (math.radians(90), 0, 0)

# --- engine block (chrome cylindrical V-twin) ----------------------------
engine_block = beveled_cube("engine_block", (0.45, 0.4, 0.45), bevel_offset=0.08, bevel_segments=4, loc=(0, 0.25, 0), parent=chopper, mat=MAT_ENGINE_BLACK)
# 2 cylinder heads (chrome)
for side, ang in [("F", math.radians(20)), ("B", math.radians(-30))]:
    cyl_p = empty(f"engine_cyl_{side}", (0, 0.40, 0), parent=chopper)
    cyl_p.rotation_euler = (0, 0, ang)
    cyl_body = smooth_cone(f"engine_cyl_{side}_body", r1=0.13, r2=0.13, depth=0.30, segs=16, loc=(0, 0.18, 0), parent=cyl_p, mat=MAT_ENGINE_CHROME)
    # 4 cooling fins
    for k in range(4):
        ky = 0.06 + k * 0.06
        fin = smooth_cone(f"engine_cyl_{side}_fin_{k}", r1=0.17, r2=0.17, depth=0.03, segs=14, loc=(0, ky, 0), parent=cyl_p, mat=MAT_ENGINE_CHROME)
    # top cap
    top = smooth_cone(f"engine_cyl_{side}_top", r1=0.13, r2=0.09, depth=0.06, segs=12, loc=(0, 0.36, 0), parent=cyl_p, mat=MAT_ENGINE_BLACK)

# --- handlebar (curved bar with chrome handles) -------------------------
handlebar_p = empty("handlebar", (1.5, 1.0, 0), parent=chopper)
# main central bar (curved cone going down a bit)
hb_central = smooth_cone("hb_central", r1=0.04, r2=0.04, depth=0.8, segs=14, loc=(0, 0, 0), parent=handlebar_p, mat=MAT_CHROME)
hb_central.rotation_euler = (math.radians(90), 0, 0)
# 2 grips (chrome with rubber wrap)
for side, dz in [("L", 0.40), ("R", -0.40)]:
    # connecting riser
    riser = smooth_cone(f"hb_riser_{side}", r1=0.04, r2=0.04, depth=0.15, segs=10, loc=(0, 0.08, dz), parent=handlebar_p, mat=MAT_CHROME)
    riser.rotation_euler = (math.radians(45 if side == "L" else -45), 0, 0)
    # grip
    grip = smooth_cone(f"hb_grip_{side}", r1=0.05, r2=0.05, depth=0.20, segs=14, loc=(0, 0.18, dz + (0.10 if side == "L" else -0.10)), parent=handlebar_p, mat=MAT_LEATHER)
    grip.rotation_euler = (math.radians(90), 0, 0)
    # end cap
    cap = smooth_sphere(f"hb_cap_{side}", r=0.05, segs=14, rings=10, loc=(0, 0.20, dz + (0.20 if side == "L" else -0.20)), parent=handlebar_p, mat=MAT_CHROME)
# 2 blinkers (orange, at handlebar tips)
blinkers = []
for side, dz in [("L", 0.55), ("R", -0.55)]:
    bl = smooth_sphere(f"blinker_{side}", r=0.06, segs=14, rings=10, loc=(0, 0.18, dz), parent=handlebar_p, mat=MAT_BLINKER)
    bl.scale = (0.7, 1.2, 1.0)
    blinkers.append(bl)

# --- 2 fourches avant (forks) ---------------------------------------
for side, dz in [("L", 0.12), ("R", -0.12)]:
    fork = smooth_cone(f"fork_{side}", r1=0.05, r2=0.05, depth=0.95, segs=12, loc=(1.5, 0.45, dz), parent=chopper, mat=MAT_FORK)
    fork.rotation_euler = (math.radians(180 - 15), 0, 0)
    # spring detail (chrome ribbed)
    for k in range(5):
        ky = 0.20 + k * 0.10
        ring = smooth_cone(f"fork_{side}_r_{k}", r1=0.06, r2=0.06, depth=0.025, segs=12, loc=(1.5, ky, dz), parent=chopper, mat=MAT_CHROME)
        ring.rotation_euler = (math.radians(90), 0, 0)

# --- saddle (leather seat) --------------------------------------------
def make_saddle(name, parent):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=18, radius=0.20)
    bmesh.ops.scale(bm, vec=(1.5, 0.5, 0.95), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = add_obj(name, me, parent)
    o.location = (-0.5, 0.65, 0)
    me.materials.append(MAT_LEATHER)
    smooth_shade(me)
    return o

saddle = make_saddle("saddle", chopper)
# stitching detail (line of small spheres)
for k in range(8):
    kx = -0.30 + k * 0.08
    stitch = smooth_sphere(f"stitch_{k}", r=0.012, segs=8, rings=6, loc=(-0.50 + kx, 0.72, 0), parent=chopper, mat=MAT_LEATHER_STITCH)

# small passenger pad behind main saddle
passenger = make_saddle("passenger_seat", chopper)
passenger.location = (-0.85, 0.60, 0)
passenger.scale = (0.5, 1.0, 0.6)

# --- 2 exhausts chrome cylindriques longs --------------------------
for side, dz in [("L", 0.30), ("R", -0.30)]:
    # main pipe
    pipe = smooth_cone(f"exhaust_{side}", r1=0.07, r2=0.08, depth=1.5, segs=16, loc=(-0.7, 0.30, dz), parent=chopper, mat=MAT_EXHAUST)
    pipe.rotation_euler = (0, math.radians(85), 0)
    # tip (slightly larger)
    tip = smooth_cone(f"exhaust_{side}_tip", r1=0.10, r2=0.10, depth=0.15, segs=16, loc=(-1.55, 0.30, dz), parent=chopper, mat=MAT_EXHAUST)
    tip.rotation_euler = (0, math.radians(90), 0)
    # heat shield (around middle of pipe)
    shield = smooth_cone(f"exhaust_{side}_shield", r1=0.09, r2=0.09, depth=0.5, segs=14, loc=(-1.0, 0.30, dz), parent=chopper, mat=MAT_CHROME)
    shield.rotation_euler = (0, math.radians(90), 0)

# --- headlight assembly --------------------------------------------
headlight_p = empty("headlight_p", (1.85, 0.60, 0), parent=chopper)
# housing (chrome)
hl_housing = smooth_sphere("hl_housing", r=0.18, segs=24, rings=16, loc=(0, 0, 0), parent=headlight_p, mat=MAT_CHROME)
hl_housing.scale = (0.7, 1.0, 1.0)
# lens
hl_lens = smooth_sphere("hl_lens", r=0.15, segs=20, rings=14, loc=(0.06, 0, 0), parent=headlight_p, mat=MAT_HEADLIGHT)
hl_lens.scale = (0.4, 1.0, 1.0)
# halo
hl_halo = smooth_sphere("hl_halo", r=0.35, segs=18, rings=12, loc=(0.10, 0, 0), parent=headlight_p, mat=MAT_HL_HALO)
hl_halo.scale = (0.4, 1.0, 1.0)

# --- 2 mirrors ---------------------------------------------------
for side, dz in [("L", 0.40), ("R", -0.40)]:
    mr_p = empty(f"mirror_p_{side}", (1.5, 1.15, dz), parent=chopper)
    # arm
    arm = smooth_cone(f"mirror_arm_{side}", r1=0.025, r2=0.025, depth=0.25, segs=10, loc=(0, 0.10, 0), parent=mr_p, mat=MAT_CHROME)
    arm.rotation_euler = (math.radians(-20), 0, 0)
    # glass
    glass = smooth_sphere(f"mirror_glass_{side}", r=0.10, segs=18, rings=12, loc=(0, 0.22, 0), parent=mr_p, mat=MAT_MIRROR)
    glass.scale = (0.4, 1.0, 1.4)

# --- chain (between front and back wheels, low) -----------------------
# approx 12 small connected cubes
for k in range(12):
    kx = -1.0 + k * 0.17
    link = beveled_cube(f"chain_{k}", (0.06, 0.05, 0.08), bevel_offset=0.01, bevel_segments=2, loc=(kx, -0.10, 0.30), parent=chopper, mat=MAT_CHAIN)

# --- pedals + foot rest -----------------------------------------------
for side, dz in [("L", 0.25), ("R", -0.25)]:
    rest_p = empty(f"footrest_p_{side}", (-0.10, 0.10, dz), parent=chopper)
    # support arm
    arm = smooth_cone(f"footrest_{side}_arm", r1=0.02, r2=0.02, depth=0.20, segs=10, loc=(0, 0, 0), parent=rest_p, mat=MAT_CHROME)
    arm.rotation_euler = (0, 0, math.radians(90))
    # foot peg (chrome cylinder)
    peg = smooth_cone(f"footrest_{side}_peg", r1=0.05, r2=0.05, depth=0.10, segs=14, loc=(0, 0, 0.10 if side == "L" else -0.10), parent=rest_p, mat=MAT_CHROME)
    peg.rotation_euler = (math.radians(90), 0, 0)
    # rubber grip
    grip = smooth_cone(f"footrest_{side}_grip", r1=0.05, r2=0.05, depth=0.04, segs=14, loc=(0, 0, 0.18 if side == "L" else -0.18), parent=rest_p, mat=MAT_LEATHER)
    grip.rotation_euler = (math.radians(90), 0, 0)

# --- license plate (back) ------------------------------------------
license_plate = beveled_cube("license", (0.05, 0.18, 0.30), bevel_offset=0.02, bevel_segments=2, loc=(-1.65, 0.55, 0), parent=chopper, mat=MAT_LICENSE)

# --- 2 back blinkers ----------------------------------------------
back_blinkers = []
for side, dz in [("L", 0.18), ("R", -0.18)]:
    bb = smooth_sphere(f"back_blinker_{side}", r=0.05, segs=14, rings=10, loc=(-1.7, 0.55, dz), parent=chopper, mat=MAT_BLINKER)
    bb.scale = (0.7, 1.2, 1.0)
    back_blinkers.append(bb)

# --- 4 ceiling lamps --------------------------------------------
ceiling_lamps = []
for i, (lx, lz) in enumerate([(-4, 4), (4, 4), (-4, -4), (4, -4)]):
    lp = empty(f"clamp_{i}", (lx, 5.8, lz))
    rod = smooth_cone(f"clamp_{i}_rod", r1=0.04, r2=0.04, depth=0.40, segs=10, loc=(0, -0.20, 0), parent=lp, mat=MAT_LAMP_CASE)
    rod.rotation_euler = (math.radians(90), 0, 0)
    shade = smooth_cone(f"clamp_{i}_shade", r1=0.30, r2=0.18, depth=0.25, segs=20, loc=(0, -0.45, 0), parent=lp, mat=MAT_LAMP_CASE)
    shade.rotation_euler = (math.radians(180), 0, 0)
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

# 2 wheels rotate fast
for w in [front_wheel_p, back_wheel_p]:
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        kf_rot(w, f, (tt * math.pi * 24, 0, 0))  # 12 turns/loop

# chopper subtle bob + tilt (multi-axis)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    by = 0.7 + 0.04 * math.sin(tt * math.pi * 5.0)
    rotY = math.radians(20) * math.sin(tt * math.pi * 2.0)
    tilt = math.radians(3) * math.sin(tt * math.pi * 3.0)
    kf_loc(chopper, f, (0, by, 0))
    kf_rot(chopper, f, (0, rotY, tilt))

# handlebar turns subtle (driver tourne)
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    angle = math.radians(12) * math.sin(tt * math.pi * 3.0)
    kf_rot(handlebar_p, f, (0, angle, 0))

# engine subtle vibration (high-frequency scale)
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.025 * math.sin(tt * math.pi * 60.0)  # vibration 30Hz
    kf_scale(engine_block, f, (s, s, s))

# headlight pulse intense
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    s = 1.0 + 0.15 * math.sin(tt * math.pi * 6.0)
    kf_scale(hl_lens, f, (0.4 * s, 1.0 * s, 1.0 * s))
    sh = 1.0 + 0.20 * math.sin(tt * math.pi * 6.0)
    kf_scale(hl_halo, f, (0.4 * sh, 1.0 * sh, 1.0 * sh))

# 4 blinkers alternance (front L/R + back L/R, paired)
all_blinkers = [(blinkers[0], 0), (blinkers[1], 1), (back_blinkers[0], 0), (back_blinkers[1], 1)]
for bl, pair in all_blinkers:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        # alternance : pair 0 lights up on positive sine, pair 1 on negative
        sig = math.sin(tt * math.pi * 8.0)
        if pair == 0:
            on = sig > 0
        else:
            on = sig < 0
        s = 1.4 if on else 0.5
        kf_scale(bl, f, (0.7 * s, 1.2 * s, 1.0 * s))

# 4 ceiling lamps pulse phases offset
for i, bulb in enumerate(ceiling_lamps):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.15 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(bulb, f, (s, s, s))

# --- export -----------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format='GLB',
    export_animations=True,
    export_apply=False,
)
print(f"[proc_chopper] wrote {OUT}")
