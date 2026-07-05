"""
proc_food_truck.py — 151e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué.

Food truck street food avec auvent + clients :
- camion principal cabine + cargo bevelés smooth
- fenêtre service ouverte avec auvent
- panneau menu émissif
- 8 burgers + hot dogs + pizza sur étagère
- 4 roues détaillées avec rims
- vendor silhouette inside
- 3 clients faisant la queue
- table picnic outdoor + 4 chaises
- 6 lampes guirlande festive émissives
- arbre ombrage
- chien errant
- fumée cuisine
- ciel après-midi

Animations multi-axes :
- truck subtle bob
- 4 roues lentes
- guirlande lampes pulse cycle couleurs
- fumée cuisine monte
- vendor head bob
- 3 clients tilt
- menu émissif pulse
- chien tail wag

Sortie : output/3d/pbr_foodtruck_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_foodtruck_proc.glb"))

random.seed(0xCAFF11)

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
MAT_SKY = make_mat("sky", (0.55, 0.75, 0.95), roughness=1.0, emi=(0.45, 0.65, 0.85), emi_strength=0.5)
MAT_CLOUD = make_mat("cloud", (0.95, 0.97, 1.0), roughness=1.0, alpha=0.85, emi=(0.85, 0.90, 0.95), emi_strength=0.3)
MAT_GROUND = make_mat("ground", (0.45, 0.42, 0.38), roughness=0.85)
MAT_ASPHALT = make_mat("asphalt", (0.20, 0.20, 0.22), roughness=0.85, emi=(0.05, 0.05, 0.06), emi_strength=0.2)
MAT_TRUCK_RED = make_mat("truck_red", (0.85, 0.15, 0.10), metallic=0.40, roughness=0.30, emi=(0.30, 0.05, 0.03), emi_strength=0.25)
MAT_TRUCK_WHITE = make_mat("truck_white", (0.95, 0.95, 0.96), metallic=0.40, roughness=0.30, emi=(0.30, 0.30, 0.32), emi_strength=0.20)
MAT_TRUCK_DARK = make_mat("truck_dark", (0.15, 0.15, 0.18), metallic=0.55, roughness=0.40)
MAT_WINDOW = make_mat("window", (0.20, 0.40, 0.65), metallic=0.55, roughness=0.10, alpha=0.55, emi=(0.10, 0.25, 0.50), emi_strength=0.45)
MAT_INTERIOR = make_mat("interior", (1.0, 0.85, 0.50), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.50), emi_strength=4.5)
MAT_AWNING_RED = make_mat("awning_red", (0.85, 0.15, 0.15), roughness=0.6, emi=(0.30, 0.05, 0.05), emi_strength=0.3)
MAT_AWNING_WHITE = make_mat("awning_white", (0.95, 0.95, 0.95), roughness=0.6, emi=(0.40, 0.40, 0.42), emi_strength=0.3)
MAT_MENU_BOARD = make_mat("menu_board", (0.10, 0.10, 0.10), roughness=0.5)
MAT_MENU_TEXT = make_mat("menu_text", (1.0, 0.95, 0.30), roughness=0.0, emi=(1.0, 0.95, 0.30), emi_strength=6.0)
MAT_TIRE = make_mat("tire", (0.05, 0.05, 0.05), roughness=0.85)
MAT_RIM = make_mat("rim", (0.85, 0.85, 0.92), metallic=0.95, roughness=0.15, emi=(0.25, 0.25, 0.30), emi_strength=0.3)
MAT_BURGER_BUN = make_mat("burger_bun", (0.75, 0.55, 0.30), roughness=0.7, emi=(0.20, 0.15, 0.05), emi_strength=0.2)
MAT_BURGER_PATTY = make_mat("burger_patty", (0.40, 0.20, 0.10), roughness=0.6)
MAT_BURGER_CHEESE = make_mat("burger_cheese", (1.0, 0.85, 0.20), roughness=0.4, emi=(0.40, 0.30, 0.05), emi_strength=0.4)
MAT_BURGER_LETTUCE = make_mat("burger_lettuce", (0.30, 0.55, 0.20), roughness=0.6)
MAT_HOTDOG_BREAD = make_mat("hotdog_bread", (0.85, 0.65, 0.35), roughness=0.6, emi=(0.20, 0.15, 0.05), emi_strength=0.2)
MAT_HOTDOG_SAUSAGE = make_mat("hotdog_sausage", (0.65, 0.15, 0.10), roughness=0.5)
MAT_PIZZA_BASE = make_mat("pizza_base", (0.85, 0.65, 0.30), roughness=0.6)
MAT_PIZZA_TOMATO = make_mat("pizza_tomato", (0.85, 0.20, 0.10), roughness=0.45, emi=(0.30, 0.05, 0.03), emi_strength=0.3)
MAT_PERSON_HEAD = make_mat("person_head", (0.95, 0.75, 0.55), roughness=0.7)
MAT_PERSON_BODY = make_mat("person_body", (0.20, 0.25, 0.30), roughness=0.7)
MAT_PERSON_R = make_mat("person_r", (0.65, 0.15, 0.10), roughness=0.7)
MAT_PERSON_B = make_mat("person_b", (0.15, 0.30, 0.65), roughness=0.7)
MAT_PERSON_G = make_mat("person_g", (0.15, 0.55, 0.30), roughness=0.7)
MAT_TABLE_WOOD = make_mat("table_wood", (0.45, 0.30, 0.18), roughness=0.6)
MAT_CHAIR_RED = make_mat("chair_red", (0.85, 0.20, 0.15), roughness=0.6)
MAT_TREE_TRUNK = make_mat("tree_trunk", (0.30, 0.20, 0.12), roughness=0.9)
MAT_TREE_LEAVES = make_mat("tree_leaves", (0.20, 0.55, 0.25), roughness=0.85, emi=(0.08, 0.20, 0.08), emi_strength=0.3)
MAT_LIGHT_R = make_mat("light_r", (1.0, 0.20, 0.20), roughness=0.0, emi=(1.0, 0.20, 0.20), emi_strength=8.0)
MAT_LIGHT_B = make_mat("light_b", (0.20, 0.50, 1.0), roughness=0.0, emi=(0.20, 0.50, 1.0), emi_strength=8.0)
MAT_LIGHT_Y = make_mat("light_y", (1.0, 0.95, 0.20), roughness=0.0, emi=(1.0, 0.95, 0.20), emi_strength=8.0)
MAT_LIGHT_G = make_mat("light_g", (0.20, 1.0, 0.30), roughness=0.0, emi=(0.20, 1.0, 0.30), emi_strength=8.0)
MAT_CABLE = make_mat("cable", (0.10, 0.10, 0.10), roughness=0.7)
MAT_DOG = make_mat("dog", (0.65, 0.50, 0.30), roughness=0.7)
MAT_SMOKE = make_mat("smoke", (0.55, 0.55, 0.55), roughness=1.0, alpha=0.65, emi=(0.35, 0.35, 0.35), emi_strength=0.4)
MAT_CHIMNEY = make_mat("chimney", (0.30, 0.30, 0.30), metallic=0.65, roughness=0.35)
MAT_PRICE_TAG = make_mat("price_tag", (1.0, 0.95, 0.85), roughness=0.4, emi=(0.40, 0.38, 0.32), emi_strength=0.4)

# --- backdrop : sky ----------------------------------------------------
sky = beveled_cube("sky_back", (40, 0.2, 14), bevel_offset=0.05, bevel_segments=2, loc=(0, 9, 7), mat=MAT_SKY)

# 4 clouds
for i, (cx, cy, cz) in enumerate([(-10, 12, 7), (-3, 13, 8), (5, 12, 6), (11, 13, 7)]):
    cl = smooth_sphere(f"cloud_{i}", r=random.uniform(1.2, 1.7), segs=18, rings=12, loc=(cx, cy, cz), mat=MAT_CLOUD, scale=(1.6, 0.55, 1.1))

# --- ground (asphalt + grass) ------------------------------------
ground = beveled_cube("ground", (30, 0.05, 20), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.025, 0), mat=MAT_ASPHALT)
# grass patches
for i in range(4):
    gx = random.uniform(-10, 10)
    gz = random.uniform(-7, 7)
    g = beveled_cube(f"grass_{i}", (random.uniform(1.5, 3.0), 0.04, random.uniform(1.0, 2.0)), bevel_offset=0.03, bevel_segments=2, loc=(gx, 0.01, gz), mat=MAT_GROUND)

# --- arbre ombrage ----------------------------------------
tree_p = empty("tree", (5, 0, 3))
trunk = smooth_cone("trunk", r1=0.30, r2=0.20, depth=2.5, segs=14, loc=(0, 1.25, 0), parent=tree_p, mat=MAT_TREE_TRUNK)
trunk.rotation_euler = (math.radians(90), 0, 0)
# foliage cluster
for j in range(7):
    ja = j * (math.pi * 2 / 7)
    f_obj = smooth_sphere(f"foliage_{j}", r=0.9, segs=20, rings=14, loc=(math.cos(ja) * 0.7, 3.0 + random.uniform(-0.3, 0.4), math.sin(ja) * 0.7), parent=tree_p, mat=MAT_TREE_LEAVES, scale=(1.3, 1.0, 1.3))

# --- FOOD TRUCK -------------------------------------------------
truck = empty("truck", (-1, 0, 0))

# cabine (front cabin)
cabin = beveled_cube("cabin", (1.2, 1.4, 1.8), bevel_offset=0.12, bevel_segments=4, loc=(1.5, 0.85, 0), parent=truck, mat=MAT_TRUCK_RED)

# windshield
windshield = beveled_cube("windshield", (0.06, 0.55, 1.4), bevel_offset=0.05, bevel_segments=3, loc=(2.05, 1.20, 0), parent=truck, mat=MAT_WINDOW)
windshield.rotation_euler = (0, 0, math.radians(-10))

# 2 side windows
for side, dz in [("L", 0.92), ("R", -0.92)]:
    sw = beveled_cube(f"side_win_{side}", (1.0, 0.45, 0.04), bevel_offset=0.04, bevel_segments=2, loc=(1.5, 1.10, dz), parent=truck, mat=MAT_WINDOW)

# cargo box (food prep area)
cargo = beveled_cube("cargo", (2.6, 1.8, 2.0), bevel_offset=0.12, bevel_segments=4, loc=(-0.5, 1.10, 0), parent=truck, mat=MAT_TRUCK_WHITE)

# red stripe on cargo
stripe = beveled_cube("cargo_stripe", (2.7, 0.15, 2.05), bevel_offset=0.04, bevel_segments=2, loc=(-0.5, 1.05, 0), parent=truck, mat=MAT_TRUCK_RED)

# --- service window (opens on side) ---
# main service opening (large)
service_win = beveled_cube("service_win", (1.8, 0.85, 0.04), bevel_offset=0.05, bevel_segments=3, loc=(-0.5, 1.30, 1.02), parent=truck, mat=MAT_INTERIOR)

# awning above service window (red + white stripes)
awning_p = empty("awning_p", (-0.5, 2.10, 1.05), parent=truck)
awning_p.rotation_euler = (math.radians(20), 0, 0)
# alternating stripes
for k in range(7):
    kx = -0.85 + k * 0.30
    mat = MAT_AWNING_RED if k % 2 == 0 else MAT_AWNING_WHITE
    stripe_a = beveled_cube(f"awning_stripe_{k}", (0.25, 0.04, 0.85), bevel_offset=0.02, bevel_segments=2, loc=(kx, 0, 0), parent=awning_p, mat=mat)
# awning support poles
for side, dx in [("L", -0.90), ("R", 0.90)]:
    pole = smooth_cone(f"awning_pole_{side}", r1=0.04, r2=0.04, depth=0.85, segs=10, loc=(-0.5 + dx, 1.60, 1.50), parent=truck, mat=MAT_TRUCK_DARK)

# --- menu board (panneau émissif) ---
menu_p = empty("menu_p", (-1.5, 1.85, 1.10), parent=truck)
menu_board = beveled_cube("menu_board", (0.05, 0.65, 0.55), bevel_offset=0.03, bevel_segments=2, loc=(0, 0, 0), parent=menu_p, mat=MAT_MENU_BOARD)
# 5 menu items (text rows)
for k in range(5):
    ky = -0.20 + k * 0.10
    row = beveled_cube(f"menu_row_{k}", (0.02, 0.04, 0.40), bevel_offset=0.005, bevel_segments=2, loc=(-0.03, ky, 0), parent=menu_p, mat=MAT_MENU_TEXT)
# price tag in corner
price = beveled_cube("price_tag", (0.04, 0.10, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(-0.03, 0.25, 0.20), parent=menu_p, mat=MAT_PRICE_TAG)

# --- 8 burgers + hot dogs + pizza sur counter (visible through service window) ---
counter_y = 1.10
# counter inside cargo
counter = beveled_cube("counter", (2.0, 0.05, 0.45), bevel_offset=0.03, bevel_segments=2, loc=(-0.5, counter_y, 0.65), parent=truck, mat=MAT_TRUCK_WHITE)

# 4 burgers on left
for k in range(4):
    bx = -1.2 + k * 0.20
    bur_p = empty(f"burger_{k}", (bx, counter_y + 0.05, 0.65), parent=truck)
    # bottom bun
    bottom = smooth_sphere(f"burger_{k}_bot", r=0.08, segs=14, rings=10, loc=(0, 0, 0), parent=bur_p, mat=MAT_BURGER_BUN, scale=(1.0, 0.5, 1.0))
    # lettuce
    lettuce = smooth_sphere(f"burger_{k}_lett", r=0.085, segs=14, rings=10, loc=(0, 0.04, 0), parent=bur_p, mat=MAT_BURGER_LETTUCE, scale=(1.0, 0.2, 1.0))
    # patty
    patty = smooth_sphere(f"burger_{k}_pat", r=0.08, segs=14, rings=10, loc=(0, 0.07, 0), parent=bur_p, mat=MAT_BURGER_PATTY, scale=(1.0, 0.3, 1.0))
    # cheese
    cheese = smooth_sphere(f"burger_{k}_che", r=0.08, segs=14, rings=10, loc=(0, 0.10, 0), parent=bur_p, mat=MAT_BURGER_CHEESE, scale=(1.0, 0.2, 1.0))
    # top bun
    top = smooth_sphere(f"burger_{k}_top", r=0.08, segs=14, rings=10, loc=(0, 0.14, 0), parent=bur_p, mat=MAT_BURGER_BUN, scale=(1.0, 0.6, 1.0))

# 2 hotdogs in middle
for k in range(2):
    hx = -0.35 + k * 0.20
    hd_p = empty(f"hotdog_{k}", (hx, counter_y + 0.05, 0.65), parent=truck)
    bread = smooth_cone(f"hotdog_{k}_bread", r1=0.06, r2=0.06, depth=0.20, segs=14, loc=(0, 0, 0), parent=hd_p, mat=MAT_HOTDOG_BREAD)
    bread.rotation_euler = (0, math.radians(90), 0)
    sausage = smooth_cone(f"hotdog_{k}_saus", r1=0.04, r2=0.04, depth=0.25, segs=12, loc=(0, 0.06, 0), parent=hd_p, mat=MAT_HOTDOG_SAUSAGE)
    sausage.rotation_euler = (0, math.radians(90), 0)

# 1 pizza on right
pizza_p = empty("pizza", (0.20, counter_y + 0.05, 0.65), parent=truck)
pizza_base = smooth_cone("pizza_base", r1=0.20, r2=0.20, depth=0.03, segs=24, loc=(0, 0, 0), parent=pizza_p, mat=MAT_PIZZA_BASE)
pizza_base.rotation_euler = (math.radians(90), 0, 0)
# tomato sauce layer
sauce = smooth_cone("pizza_sauce", r1=0.18, r2=0.18, depth=0.015, segs=22, loc=(0, 0.025, 0), parent=pizza_p, mat=MAT_PIZZA_TOMATO)
sauce.rotation_euler = (math.radians(90), 0, 0)
# 8 cheese bits
for k in range(8):
    a = k * (math.pi * 2 / 8)
    ch = smooth_sphere(f"pizza_cheese_{k}", r=0.025, segs=10, rings=8, loc=(math.cos(a) * 0.10, 0.04, math.sin(a) * 0.10), parent=pizza_p, mat=MAT_BURGER_CHEESE, scale=(1.0, 0.3, 1.0))

# --- vendor inside truck ---
vendor_p = empty("vendor_p", (-0.6, 1.20, 0.45), parent=truck)
vendor_torso = beveled_cube("vendor_torso", (0.30, 0.50, 0.18), bevel_offset=0.05, bevel_segments=3, loc=(0, 0, 0), parent=vendor_p, mat=MAT_AWNING_RED)
vendor_head = smooth_sphere("vendor_head", r=0.16, segs=18, rings=14, loc=(0, 0.35, 0), parent=vendor_p, mat=MAT_PERSON_HEAD)
# chef hat (cylinder + top fluffy)
hat_base = smooth_cone("vendor_hat_base", r1=0.13, r2=0.13, depth=0.10, segs=18, loc=(0, 0.50, 0), parent=vendor_p, mat=MAT_TRUCK_WHITE)
hat_base.rotation_euler = (math.radians(90), 0, 0)
hat_top = smooth_sphere("vendor_hat_top", r=0.14, segs=18, rings=14, loc=(0, 0.60, 0), parent=vendor_p, mat=MAT_TRUCK_WHITE)
# 2 arms
for side, dx in [("L", -0.22), ("R", 0.22)]:
    arm = beveled_cube(f"vendor_arm_{side}", (0.08, 0.30, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(dx, -0.10, 0), parent=vendor_p, mat=MAT_AWNING_RED)

# --- chimney avec smoke ----------------
chim_p = empty("chim_p", (-1.0, 2.0, -0.5), parent=truck)
chim = smooth_cone("chim", r1=0.08, r2=0.10, depth=0.40, segs=12, loc=(0, 0.2, 0), parent=chim_p, mat=MAT_CHIMNEY)
chim.rotation_euler = (math.radians(90), 0, 0)
# 4 smoke puffs
smoke_puffs = []
for k in range(4):
    py = 0.45 + k * 0.25
    pr = 0.10 + k * 0.05
    puff = smooth_sphere(f"smoke_{k}", r=pr, segs=12, rings=8, loc=(0, py, 0), parent=chim_p, mat=MAT_SMOKE)
    smoke_puffs.append((puff, k))

# --- 4 roues détaillées ---
wheels = []
wheel_data = [(2.0, 1.0), (2.0, -1.0), (-1.4, 1.0), (-1.4, -1.0)]
for i, (wx, wz) in enumerate(wheel_data):
    w_p = empty(f"wheel_{i}", (wx, 0.45, wz), parent=truck)
    tire = smooth_cone(f"wheel_{i}_tire", r1=0.45, r2=0.45, depth=0.25, segs=24, loc=(0, 0, 0), parent=w_p, mat=MAT_TIRE)
    tire.rotation_euler = (0, math.radians(90), 0)
    # alloy rim
    rim = smooth_cone(f"wheel_{i}_rim", r1=0.28, r2=0.28, depth=0.27, segs=20, loc=(0, 0, 0), parent=w_p, mat=MAT_RIM)
    rim.rotation_euler = (0, math.radians(90), 0)
    # 6 spokes
    for k in range(6):
        ka = k * (math.pi / 3)
        spoke = beveled_cube(f"wheel_{i}_spoke_{k}", (0.04, 0.04, 0.26), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0), parent=w_p, mat=MAT_RIM)
        spoke.rotation_euler = (ka, 0, 0)
    wheels.append(w_p)

# 2 headlights
for side, dz in [("L", 0.50), ("R", -0.50)]:
    hl = smooth_sphere(f"headlight_{side}", r=0.12, segs=14, rings=10, loc=(2.10, 0.85, dz), parent=truck, mat=MAT_INTERIOR, scale=(0.5, 1.0, 1.0))

# --- 3 clients faisant la queue ---
clients = []
for i, (cx, cz, mat) in enumerate([(-3.0, 1.5, MAT_PERSON_R), (-3.0, 0.8, MAT_PERSON_B), (-3.0, 0.0, MAT_PERSON_G)]):
    c_p = empty(f"client_{i}", (cx, 0, cz))
    body = beveled_cube(f"client_{i}_body", (0.22, 0.60, 0.14), bevel_offset=0.05, bevel_segments=3, loc=(0, 0.60, 0), parent=c_p, mat=mat)
    head = smooth_sphere(f"client_{i}_head", r=0.13, segs=14, rings=10, loc=(0, 1.05, 0), parent=c_p, mat=MAT_PERSON_HEAD)
    # 2 legs
    for side, dx in [("L", -0.07), ("R", 0.07)]:
        leg = beveled_cube(f"client_{i}_l_{side}", (0.08, 0.30, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(dx, 0.15, 0), parent=c_p, mat=MAT_TRUCK_DARK)
    # 2 arms
    for side, dx in [("L", -0.20), ("R", 0.20)]:
        arm = beveled_cube(f"client_{i}_a_{side}", (0.08, 0.30, 0.10), bevel_offset=0.02, bevel_segments=2, loc=(dx, 0.55, 0), parent=c_p, mat=mat)
    clients.append(c_p)

# --- table picnic outdoor + 4 chairs ---
picnic_p = empty("picnic", (5.5, 0, -2))
# table
table_top = beveled_cube("picnic_top", (1.5, 0.08, 0.8), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.80, 0), parent=picnic_p, mat=MAT_TABLE_WOOD)
# 4 legs
for i, (lx, lz) in enumerate([(0.65, 0.35), (-0.65, 0.35), (0.65, -0.35), (-0.65, -0.35)]):
    leg = beveled_cube(f"picnic_leg_{i}", (0.08, 0.80, 0.08), bevel_offset=0.02, bevel_segments=2, loc=(lx, 0.40, lz), parent=picnic_p, mat=MAT_TABLE_WOOD)
# 4 chairs
for i, (cx, cz) in enumerate([(1.2, 0), (-1.2, 0), (0, 0.9), (0, -0.9)]):
    chair_p = empty(f"chair_{i}", (cx, 0, cz), parent=picnic_p)
    seat = beveled_cube(f"chair_{i}_seat", (0.40, 0.06, 0.40), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.45, 0), parent=chair_p, mat=MAT_CHAIR_RED)
    # backrest
    back = beveled_cube(f"chair_{i}_back", (0.40, 0.40, 0.04), bevel_offset=0.03, bevel_segments=2, loc=(0, 0.65, -0.18), parent=chair_p, mat=MAT_CHAIR_RED)
    for k, (klx, klz) in enumerate([(0.15, 0.15), (-0.15, 0.15), (0.15, -0.15), (-0.15, -0.15)]):
        leg = beveled_cube(f"chair_{i}_l_{k}", (0.04, 0.45, 0.04), bevel_offset=0.01, bevel_segments=2, loc=(klx, 0.22, klz), parent=chair_p, mat=MAT_TRUCK_DARK)

# --- 6 lampes guirlande festive (string lights) ---
lights = []
light_mats = [MAT_LIGHT_R, MAT_LIGHT_B, MAT_LIGHT_Y, MAT_LIGHT_G, MAT_LIGHT_R, MAT_LIGHT_B]
# cable spanning from truck top to tree
cable_segs = 6
cable_start = (-1.5, 3.10, 1.10)
cable_end = (5, 3.50, 3)
for k in range(cable_segs):
    t = (k + 0.5) / cable_segs
    # sagging cable (parabolic dip)
    sag = -0.30 * 4 * t * (1 - t)
    cx = cable_start[0] + (cable_end[0] - cable_start[0]) * t
    cy = cable_start[1] + (cable_end[1] - cable_start[1]) * t + sag
    cz = cable_start[2] + (cable_end[2] - cable_start[2]) * t
    # light bulb
    bulb = smooth_sphere(f"light_{k}", r=0.10, segs=14, rings=10, loc=(cx, cy, cz), mat=light_mats[k])
    lights.append((bulb, k))
    # cable segment
    cable = beveled_cube(f"cable_{k}", (0.02, 0.02, 1.0), bevel_offset=0.005, bevel_segments=2, loc=(cx, cy + 0.05, cz), mat=MAT_CABLE)
    # orient cable along path
    dx = cable_end[0] - cable_start[0]
    dz = cable_end[2] - cable_start[2]
    cable.rotation_euler = (0, math.atan2(dx, dz), 0)
    cable.scale = (1.0, 1.0, 1.0 / cable_segs * (cable_end[2] - cable_start[2]) if abs(cable_end[2] - cable_start[2]) > 0.1 else 1.0)

# --- chien errant ---
dog_p = empty("dog", (2.5, 0, -3))
dog_body = smooth_sphere("dog_body", r=0.25, segs=18, rings=14, loc=(0, 0.30, 0), parent=dog_p, mat=MAT_DOG, scale=(1.7, 0.8, 0.9))
dog_head = smooth_sphere("dog_head", r=0.16, segs=16, rings=12, loc=(0.40, 0.40, 0), parent=dog_p, mat=MAT_DOG, scale=(1.3, 1.0, 0.95))
# ears
for side, dz in [("L", 0.10), ("R", -0.10)]:
    ear = smooth_cone(f"dog_ear_{side}", r1=0.06, r2=0.0, depth=0.12, segs=8, loc=(0.40, 0.55, dz), parent=dog_p, mat=MAT_DOG)
# legs
for i, (lx, lz) in enumerate([(0.20, 0.15), (0.20, -0.15), (-0.20, 0.15), (-0.20, -0.15)]):
    leg = beveled_cube(f"dog_leg_{i}", (0.08, 0.20, 0.08), bevel_offset=0.02, bevel_segments=2, loc=(lx, 0.10, lz), parent=dog_p, mat=MAT_DOG)
# tail (animated)
tail_p = empty("dog_tail_p", (-0.30, 0.40, 0), parent=dog_p)
tail = smooth_cone("dog_tail", r1=0.04, r2=0.02, depth=0.25, segs=8, loc=(-0.10, 0, 0), parent=tail_p, mat=MAT_DOG)
tail.rotation_euler = (0, 0, math.radians(120))

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

# truck subtle bob
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    by = 0 + 0.02 * math.sin(tt * math.pi * 5.0)
    kf_loc(truck, f, (-1, by, 0))

# 4 wheels slow rotate (idling)
for w in wheels:
    for f in range(1, FRAMES + 1, 3):
        tt = (f - 1) / (FRAMES - 1)
        kf_rot(w, f, (tt * math.pi * 1.0, 0, 0))

# 6 guirlande lights pulse (cycle different phases)
for bulb, idx in lights:
    phase = idx * 0.5
    for f in range(1, FRAMES + 1, 2):
        tt = (f - 1) / (FRAMES - 1)
        s = 1.0 + 0.30 * math.sin(tt * math.pi * 5.0 + phase)
        kf_scale(bulb, f, (s, s, s))

# 4 smoke puffs rise + scale
for puff, k in smoke_puffs:
    phase = k * 8
    base_y = 0.45 + k * 0.25
    for f in range(1, FRAMES + 1, 3):
        local_f = (f + phase) % 60
        lt = local_f / 60
        dy = base_y + lt * 1.5
        dx = math.sin(lt * math.pi * 3.0) * 0.15
        kf_loc(puff, f, (dx, dy, 0))
        s = 0.5 + lt * 1.5
        kf_scale(puff, f, (s, s, s))

# vendor head bob
for f in range(1, FRAMES + 1, 3):
    tt = (f - 1) / (FRAMES - 1)
    bob = math.radians(5) * math.sin(tt * math.pi * 4.0)
    kf_rot(vendor_p, f, (bob, 0, 0))

# 3 clients tilt
for i, c_p in enumerate(clients):
    phase = i * 0.5
    for f in range(1, FRAMES + 1, 4):
        tt = (f - 1) / (FRAMES - 1)
        tilt = math.radians(4) * math.sin(tt * math.pi * 4.0 + phase)
        kf_rot(c_p, f, (tilt, 0, 0))

# menu_text pulse
for k in range(5):
    row = bpy.data.objects.get(f"menu_row_{k}")
    if row:
        phase = k * 0.4
        for f in range(1, FRAMES + 1, 4):
            tt = (f - 1) / (FRAMES - 1)
            s = 1.0 + 0.10 * math.sin(tt * math.pi * 5.0 + phase)
            kf_scale(row, f, (s, s, s))

# dog tail wag
for f in range(1, FRAMES + 1, 2):
    tt = (f - 1) / (FRAMES - 1)
    wag = math.radians(30) * math.sin(tt * math.pi * 10.0)
    kf_rot(tail_p, f, (0, wag, 0))

# dog body slight tilt (excitement)
for f in range(1, FRAMES + 1, 4):
    tt = (f - 1) / (FRAMES - 1)
    bob = 0.03 * math.sin(tt * math.pi * 8.0)
    kf_loc(dog_p, f, (2.5, bob, -3))

# clouds drift slow
for i in range(4):
    cl = bpy.data.objects.get(f"cloud_{i}")
    if cl:
        base_x = cl.location.x
        base_z = cl.location.z
        for f in range(1, FRAMES + 1, 5):
            tt = (f - 1) / (FRAMES - 1)
            dx = base_x + 0.4 * math.sin(tt * math.pi * 1.5 + i * 0.6)
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
print(f"[proc_foodtruck] wrote {OUT}")
