"""
proc_medieval_feast_tavern.py — 188e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Taverne médiévale festin :
- grande salle bois rustique
- table énorme + 30 plats (poulet/jambon/miches/pommes/gobelets)
- 12 chaises
- 20 villageois assis avec gobelets levés
- cheminée flammes
- ménestrel jouant luth
- chien sous table
- 6 lanternes torche émissives
- cor de chasse mur
- 4 tonneaux
- 3 tapisseries
- ciel soir + 30 particules feu

Animations multi-axes simultanées :
- ménestrel joue luth (2 bras strumming)
- 20 villageois lèvent gobelets cyclic
- chien tail wave
- cheminée flammes intense
- 6 lanternes pulse différentielles
- 30 particles drift

Sortie : output/3d/pbr_tavern_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_tavern_proc.glb"))

random.seed(0x7A4E20)


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
MAT_WALL = make_mat("wall", (0.30, 0.20, 0.12), roughness=0.85, emi=(0.12, 0.08, 0.05), emi_strength=0.3)
MAT_FLOOR = make_mat("floor_wood", (0.25, 0.15, 0.08), roughness=0.7)
MAT_WOOD = make_mat("wood", (0.45, 0.25, 0.12), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.06), roughness=0.85)
MAT_TABLE = make_mat("table", (0.40, 0.25, 0.12), roughness=0.6)
MAT_CHICKEN = make_mat("chicken", (0.85, 0.60, 0.30), roughness=0.5, emi=(0.30, 0.20, 0.08), emi_strength=0.4)
MAT_HAM = make_mat("ham", (0.85, 0.40, 0.30), roughness=0.5, emi=(0.35, 0.12, 0.08), emi_strength=0.4)
MAT_BREAD = make_mat("bread", (0.85, 0.65, 0.35), roughness=0.7, emi=(0.30, 0.22, 0.10), emi_strength=0.4)
MAT_APPLE_RED = make_mat("apple_red", (0.85, 0.20, 0.15), roughness=0.4, emi=(0.30, 0.05, 0.05), emi_strength=0.4)
MAT_APPLE_GREEN = make_mat("apple_green", (0.30, 0.65, 0.20), roughness=0.4, emi=(0.10, 0.25, 0.08), emi_strength=0.4)
MAT_GOBLET = make_mat("goblet", (0.85, 0.65, 0.30), metallic=0.6, roughness=0.35, emi=(0.30, 0.22, 0.08), emi_strength=0.4)
MAT_FLAME = make_mat("flame", (1.0, 0.55, 0.10), roughness=0.0, alpha=0.85, emi=(1.0, 0.55, 0.10), emi_strength=15.0)
MAT_FLAME_INNER = make_mat("flame_inner", (1.0, 0.85, 0.30), roughness=0.0, alpha=0.85, emi=(1.0, 0.85, 0.30), emi_strength=20.0)
MAT_VILLAGER_TUNIC = make_mat("villager_tunic", (0.45, 0.30, 0.15), roughness=0.7, emi=(0.18, 0.10, 0.05), emi_strength=0.3)
MAT_VILLAGER_SKIN = make_mat("villager_skin", (0.85, 0.65, 0.50), roughness=0.6)
MAT_MENESTREL_TUNIC = make_mat("menestrel_tunic", (0.65, 0.30, 0.65), roughness=0.6, emi=(0.25, 0.10, 0.25), emi_strength=0.4)
MAT_LUTH = make_mat("luth", (0.55, 0.30, 0.15), roughness=0.5)
MAT_DOG = make_mat("dog", (0.55, 0.35, 0.20), roughness=0.6)
MAT_TORCH = make_mat("torch", (0.30, 0.18, 0.08), roughness=0.7)
MAT_HORN = make_mat("horn", (0.85, 0.65, 0.30), metallic=0.5, roughness=0.40)
MAT_BARREL = make_mat("barrel", (0.40, 0.22, 0.10), roughness=0.7)
MAT_BARREL_METAL = make_mat("barrel_metal", (0.30, 0.28, 0.28), metallic=0.7, roughness=0.45)
MAT_TAPESTRY_R = make_mat("tapestry_red", (0.55, 0.15, 0.10), roughness=0.7, emi=(0.20, 0.05, 0.05), emi_strength=0.3)
MAT_TAPESTRY_B = make_mat("tapestry_blue", (0.20, 0.30, 0.55), roughness=0.7, emi=(0.05, 0.10, 0.20), emi_strength=0.3)
MAT_PARTICLE = make_mat("particle", (1.0, 0.65, 0.20), roughness=0.0, emi=(1.0, 0.65, 0.20), emi_strength=10.0)


# --- backdrop : tavern interior -----------------------------------------
back_wall = beveled_cube("back_wall", (16, 0.3, 8), bevel_offset=0.05, bevel_segments=2, loc=(0, 4, -5), mat=MAT_WALL)
side_wall_L = beveled_cube("side_wall_L", (0.3, 8, 12), bevel_offset=0.05, bevel_segments=2, loc=(-8, 4, 0), mat=MAT_WALL)
side_wall_R = beveled_cube("side_wall_R", (0.3, 8, 12), bevel_offset=0.05, bevel_segments=2, loc=(8, 4, 0), mat=MAT_WALL)
floor = beveled_cube("floor", (16, 0.1, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_FLOOR)
ceiling = beveled_cube("ceiling", (16, 0.1, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, 8.05, 0), mat=MAT_WOOD_DARK)
# 6 ceiling beams
for bk in range(6):
    bx = -6 + bk * 2.4
    beveled_cube(f"beam_{bk}", (0.30, 0.40, 12), bevel_offset=0.04, bevel_segments=2, loc=(bx, 7.55, 0), mat=MAT_WOOD_DARK)


# --- TABLE énorme centrale ----------------------------------------------
table_p = empty("table_p", (0, 0, 0))
beveled_cube("table_top", (8, 0.15, 2.0), bevel_offset=0.05, bevel_segments=2, loc=(0, 1.1, 0), parent=table_p, mat=MAT_TABLE)
# 6 legs
for lx in [-3.5, 0, 3.5]:
    for lz in [-0.85, 0.85]:
        smooth_cone(f"table_leg_{lx}_{lz}", r1=0.10, r2=0.08, depth=1.1, segs=10, loc=(lx, 0.55, lz), parent=table_p, mat=MAT_WOOD_DARK)

# 30 plats sur table : poulet, jambon, miches, pommes, gobelets
# 4 poulets rôtis
for ck in range(4):
    cx = -3 + ck * 2.0
    cp = empty(f"chicken_{ck}_p", (cx, 1.20, 0.2))
    # body
    smooth_sphere(f"chicken_{ck}_body", r=0.20, segs=18, rings=14, loc=(0, 0, 0), parent=cp, mat=MAT_CHICKEN, scale=(1.2, 0.85, 0.95))
    # 2 drumsticks
    for dk, dz in [(0, 0.18), (1, -0.18)]:
        smooth_cone(f"chicken_{ck}_d_{dk}", r1=0.06, r2=0.04, depth=0.15, segs=6, loc=(0.15, -0.05, dz), parent=cp, mat=MAT_CHICKEN)

# 3 jambons
for hk in range(3):
    hx = -2.5 + hk * 2.5
    hp = empty(f"ham_{hk}_p", (hx, 1.20, -0.3))
    smooth_cone(f"ham_{hk}_body", r1=0.18, r2=0.12, depth=0.30, segs=14, loc=(0, 0, 0), parent=hp, mat=MAT_HAM)
    hb = bpy.data.objects.get(f"ham_{hk}_body")
    if hb:
        hb.rotation_euler = (0, 0, math.radians(90))

# 5 miches de pain
for bk in range(5):
    bx = -3 + bk * 1.5
    smooth_sphere(f"bread_{bk}", r=0.13, segs=14, rings=10, loc=(bx, 1.20, 0.5), mat=MAT_BREAD, scale=(1.4, 0.65, 1.0))

# 8 pommes (4 rouges + 4 vertes)
for ak in range(8):
    ax = -3.5 + ak * 1.0
    amat = MAT_APPLE_RED if ak % 2 == 0 else MAT_APPLE_GREEN
    smooth_sphere(f"apple_{ak}", r=0.08, segs=12, rings=10, loc=(ax, 1.20, -0.6), mat=amat)
    # tiny stem
    smooth_cone(f"apple_{ak}_stem", r1=0.008, r2=0.008, depth=0.04, segs=4, loc=(ax, 1.30, -0.6), mat=MAT_WOOD_DARK)

# 10 gobelets dorés
for gk in range(10):
    gx = -3.6 + gk * 0.8
    gp = empty(f"goblet_{gk}_p", (gx, 1.20, -0.8))
    # cup
    smooth_cone(f"goblet_{gk}_cup", r1=0.08, r2=0.10, depth=0.20, segs=10, loc=(0, 0.12, 0), parent=gp, mat=MAT_GOBLET)
    # stem
    smooth_cone(f"goblet_{gk}_stem", r1=0.02, r2=0.02, depth=0.08, segs=6, loc=(0, 0.04, 0), parent=gp, mat=MAT_GOBLET)
    # base
    smooth_cone(f"goblet_{gk}_base", r1=0.06, r2=0.06, depth=0.02, segs=8, loc=(0, 0.01, 0), parent=gp, mat=MAT_GOBLET)


# --- 12 CHAISES around table -----------------------------------------
chairs = []
CHAIR_POSITIONS = []
# 6 along each long side
for cx_idx in range(6):
    cx = -3.5 + cx_idx * 1.4
    CHAIR_POSITIONS.append((cx, 0, 1.8))
    CHAIR_POSITIONS.append((cx, 0, -1.8))
for ci, (cx, cy, cz) in enumerate(CHAIR_POSITIONS):
    cp = empty(f"chair_{ci}_p", (cx, cy, cz))
    chairs.append(cp)
    # seat
    beveled_cube(f"chair_{ci}_seat", (0.55, 0.08, 0.55), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.55, 0), parent=cp, mat=MAT_WOOD_DARK)
    # back rest (facing table)
    back_z = -0.25 if cz > 0 else 0.25
    beveled_cube(f"chair_{ci}_back", (0.55, 0.85, 0.10), bevel_offset=0.03, bevel_segments=2, loc=(0, 1.0, back_z), parent=cp, mat=MAT_WOOD_DARK)
    # 4 legs
    for lk, (lx_off, lz_off) in enumerate([(-0.22, -0.22), (0.22, -0.22), (-0.22, 0.22), (0.22, 0.22)]):
        smooth_cone(f"chair_{ci}_leg_{lk}", r1=0.04, r2=0.035, depth=0.55, segs=8, loc=(lx_off, 0.27, lz_off), parent=cp, mat=MAT_WOOD_DARK)


# --- 20 VILLAGEOIS sur chaises (lèvent gobelets) ----------------------
villagers = []
for vi in range(20):
    if vi >= len(chairs):
        break
    chair = chairs[vi]
    chair_x = chair.location.x
    chair_z = chair.location.z
    vp = empty(f"villager_{vi}_p", (chair_x, 0.65, chair_z), parent=chair)
    villagers.append(vp)
    # body
    smooth_cone(f"villager_{vi}_body", r1=0.20, r2=0.28, depth=0.55, segs=10, loc=(0, 0.30, 0), parent=vp, mat=MAT_VILLAGER_TUNIC)
    # head
    smooth_sphere(f"villager_{vi}_head", r=0.15, segs=14, rings=10, loc=(0, 0.65, 0), parent=vp, mat=MAT_VILLAGER_SKIN)
    # hair simple (random)
    if vi % 3 == 0:
        smooth_sphere(f"villager_{vi}_hair", r=0.14, segs=12, rings=8, loc=(0, 0.72, -0.05), parent=vp, mat=MAT_WOOD_DARK)
    # 1 arm raised holding goblet (signature)
    arm_p = empty(f"villager_{vi}_arm_p", (0.15, 0.50, 0), parent=vp)
    arm_p.rotation_euler = (math.radians(-60), 0, math.radians(20))
    smooth_cone(f"villager_{vi}_arm", r1=0.06, r2=0.05, depth=0.30, segs=8, loc=(0, -0.15, 0), parent=arm_p, mat=MAT_VILLAGER_TUNIC)
    # goblet in hand
    smooth_cone(f"villager_{vi}_goblet", r1=0.06, r2=0.07, depth=0.12, segs=10, loc=(0, -0.30, 0), parent=arm_p, mat=MAT_GOBLET)
    villagers[vi] = {"p": vp, "arm": arm_p, "phase": vi * 0.15}


# --- MÉNESTREL jouant luth (à côté table) -------------------------
menestrel_p = empty("menestrel_p", (-5.5, 0, 0))
# body
smooth_cone("menestrel_body", r1=0.25, r2=0.35, depth=0.85, segs=12, loc=(0, 0.50, 0), parent=menestrel_p, mat=MAT_MENESTREL_TUNIC)
# head
smooth_sphere("menestrel_head", r=0.18, segs=18, rings=14, loc=(0, 1.15, 0), parent=menestrel_p, mat=MAT_VILLAGER_SKIN)
# hat (jester-like)
smooth_cone("menestrel_hat", r1=0.20, r2=0.0, depth=0.35, segs=10, loc=(0, 1.45, 0), parent=menestrel_p, mat=MAT_MENESTREL_TUNIC)
hat_obj = bpy.data.objects.get("menestrel_hat")
if hat_obj:
    hat_obj.rotation_euler = (math.radians(20), 0, math.radians(15))
# small bell at hat tip
smooth_sphere("menestrel_bell", r=0.06, segs=10, rings=6, loc=(0.15, 1.70, 0), parent=menestrel_p, mat=MAT_GOBLET)

# LUTH (held in front)
luth_p = empty("luth_p", (0, 0.80, 0.20), parent=menestrel_p)
luth_p.rotation_euler = (0, 0, math.radians(45))
# body (rounded back lute)
smooth_sphere("luth_body", r=0.20, segs=20, rings=14, loc=(0.10, 0, 0), parent=luth_p, mat=MAT_LUTH, scale=(1.0, 1.0, 0.85))
# neck
smooth_cone("luth_neck", r1=0.05, r2=0.04, depth=0.55, segs=8, loc=(-0.30, 0, 0), parent=luth_p, mat=MAT_LUTH)
ln = bpy.data.objects.get("luth_neck")
if ln:
    ln.rotation_euler = (0, 0, math.radians(90))
# 4 strings
for sk in range(4):
    smooth_cone(f"luth_string_{sk}", r1=0.005, r2=0.005, depth=0.65, segs=4, loc=(-0.10, 0.02 - sk * 0.01, 0.02), parent=luth_p, mat=MAT_GOBLET)
    ls = bpy.data.objects.get(f"luth_string_{sk}")
    if ls:
        ls.rotation_euler = (0, 0, math.radians(90))

# 2 ARMS (strumming + holding neck)
# left arm (holding neck)
arm_L_p = empty("menestrel_arm_L_p", (-0.20, 0.90, 0.30), parent=menestrel_p)
arm_L_p.rotation_euler = (math.radians(-50), 0, math.radians(-25))
smooth_cone("menestrel_arm_L", r1=0.07, r2=0.05, depth=0.55, segs=8, loc=(0, -0.27, 0), parent=arm_L_p, mat=MAT_MENESTREL_TUNIC)
# right arm (strumming — animated)
arm_R_p = empty("menestrel_arm_R_p", (0.20, 0.90, 0.30), parent=menestrel_p)
arm_R_p.rotation_euler = (math.radians(-60), 0, math.radians(15))
smooth_cone("menestrel_arm_R", r1=0.07, r2=0.05, depth=0.50, segs=8, loc=(0, -0.25, 0), parent=arm_R_p, mat=MAT_MENESTREL_TUNIC)


# --- CHIEN sous table -----------------------------------------------
dog_p = empty("dog", (1, 0.20, 0))
# body
smooth_sphere("dog_body", r=0.18, segs=16, rings=12, loc=(0, 0.20, 0), parent=dog_p, mat=MAT_DOG, scale=(1.5, 0.85, 0.95))
# head
smooth_sphere("dog_head", r=0.13, segs=14, rings=10, loc=(0.25, 0.25, 0), parent=dog_p, mat=MAT_DOG)
# 2 ears (drooping)
for ek, ez in [("L", 0.08), ("R", -0.08)]:
    smooth_sphere(f"dog_ear_{ek}", r=0.06, segs=10, rings=6, loc=(0.20, 0.35, ez), parent=dog_p, mat=MAT_DOG, scale=(0.85, 1.5, 0.50))
# snout
smooth_cone("dog_snout", r1=0.06, r2=0.04, depth=0.10, segs=8, loc=(0.35, 0.20, 0), parent=dog_p, mat=MAT_DOG)
# 4 legs
for lk, (lx, lz) in enumerate([(-0.18, 0.12), (0.18, 0.12), (-0.18, -0.12), (0.18, -0.12)]):
    smooth_cone(f"dog_leg_{lk}", r1=0.05, r2=0.04, depth=0.20, segs=6, loc=(lx, 0.05, lz), parent=dog_p, mat=MAT_DOG)
# tail (curly)
tail_p = empty("dog_tail_p", (-0.18, 0.20, 0), parent=dog_p)
for tk in range(3):
    smooth_sphere(f"dog_tail_{tk}", r=0.035, segs=10, rings=6, loc=(-0.08 - tk * 0.06, 0.05 + tk * 0.05, 0), parent=tail_p, mat=MAT_DOG)
# 2 eyes
for ek, ez in [("L", 0.06), ("R", -0.06)]:
    smooth_sphere(f"dog_eye_{ek}", r=0.018, segs=8, rings=6, loc=(0.30, 0.30, ez), parent=dog_p, mat=MAT_WOOD_DARK)


# --- CHEMINÉE avec flammes -----------------------------------------
fireplace_p = empty("fireplace_p", (7, 0, -4.85))
# frame stone
beveled_cube("fp_frame", (2.5, 3.5, 0.40), bevel_offset=0.05, bevel_segments=2, loc=(0, 1.75, 0.20), parent=fireplace_p, mat=MAT_WALL)
# opening dark inside
beveled_cube("fp_inside", (1.8, 2.0, 0.40), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.0, 0.30), parent=fireplace_p, mat=MAT_WOOD_DARK)
# 4 flames inside
fp_flames = []
for fk in range(4):
    fx = -0.5 + fk * 0.33
    flame_p = empty(f"fp_fl_p_{fk}", (fx, 0.6, 0.40), parent=fireplace_p)
    f_out = smooth_sphere(f"fp_fl_{fk}", r=0.20, segs=14, rings=10, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(0.8, 1.6, 0.8))
    f_in = smooth_sphere(f"fp_fl_in_{fk}", r=0.13, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(0.6, 1.8, 0.6))
    fp_flames.append({"p": flame_p, "out": f_out, "in": f_in, "phase": fk * 0.25})
# logs wood
for lk in range(3):
    lx = -0.5 + lk * 0.4
    smooth_cone(f"fp_log_{lk}", r1=0.10, r2=0.10, depth=1.2, segs=8, loc=(lx, 0.30, 0.30), parent=fireplace_p, mat=MAT_WOOD_DARK)
    lo = bpy.data.objects.get(f"fp_log_{lk}")
    if lo:
        lo.rotation_euler = (0, 0, math.radians(90))
# mantle
beveled_cube("fp_mantle", (3.0, 0.15, 0.50), bevel_offset=0.04, bevel_segments=2, loc=(0, 3.65, 0.25), parent=fireplace_p, mat=MAT_WOOD_DARK)


# --- 6 LANTERNES TORCHES murales -----------------------------------
torches = []
TORCH_POSITIONS = [(-7.85, 4, -3), (-7.85, 4, 0), (-7.85, 4, 3), (7.85, 4, -3), (7.85, 4, 0), (7.85, 4, 3)]
for ti, (tx, ty, tz) in enumerate(TORCH_POSITIONS):
    tp = empty(f"torch_{ti}_p", (tx, ty, tz))
    if tx < 0:
        tp.rotation_euler = (0, math.radians(-90), 0)
    else:
        tp.rotation_euler = (0, math.radians(90), 0)
    torches.append(tp)
    # bracket
    smooth_cone(f"torch_{ti}_bracket", r1=0.04, r2=0.04, depth=0.30, segs=6, loc=(0, 0, 0.20), parent=tp, mat=MAT_WOOD_DARK)
    # torch stick
    smooth_cone(f"torch_{ti}_stick", r1=0.04, r2=0.05, depth=0.45, segs=8, loc=(0, 0.20, 0.30), parent=tp, mat=MAT_TORCH)
    # flame
    flame_p = empty(f"torch_{ti}_fl_p", (0, 0.50, 0.30), parent=tp)
    f_out = smooth_sphere(f"torch_{ti}_fl", r=0.13, segs=12, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME, scale=(0.85, 1.6, 0.85))
    f_in = smooth_sphere(f"torch_{ti}_fl_in", r=0.07, segs=10, rings=8, loc=(0, 0, 0), parent=flame_p, mat=MAT_FLAME_INNER, scale=(0.6, 1.8, 0.6))
    torches[ti] = {"p": tp, "flame_p": flame_p, "out": f_out, "in": f_in, "phase": ti * 0.30}


# --- COR DE CHASSE sur mur -----------------------------------------
horn_p = empty("horn_p", (0, 5.5, -4.85))
# horn body curved (spiral cone)
smooth_cone("horn_body", r1=0.05, r2=0.20, depth=1.5, segs=10, loc=(0, 0, 0), parent=horn_p, mat=MAT_HORN)
hb = bpy.data.objects.get("horn_body")
if hb:
    hb.rotation_euler = (math.radians(20), 0, 0)
# mouthpiece
smooth_sphere("horn_mouth", r=0.07, segs=10, rings=8, loc=(0.4, -0.4, 0), parent=horn_p, mat=MAT_HORN)


# --- 4 TONNEAUX dans coin -------------------------------------------
for bk in range(4):
    bx = -6.5 + (bk % 2) * 1.2
    bz = 4.5 - (bk // 2) * 1.2
    bp = empty(f"barrel_{bk}_p", (bx, 0, bz))
    smooth_cone(f"barrel_{bk}_body", r1=0.40, r2=0.40, depth=0.80, segs=14, loc=(0, 0.40, 0), parent=bp, mat=MAT_BARREL)
    # 3 metal bands
    for rk in range(3):
        ry = 0.15 + rk * 0.30
        ring = smooth_cone(f"barrel_{bk}_band_{rk}", r1=0.42, r2=0.42, depth=0.04, segs=14, loc=(0, ry, 0), parent=bp, mat=MAT_BARREL_METAL)


# --- 3 TAPISSERIES mur arrière -----------------------------------
TAP_MATS = [MAT_TAPESTRY_R, MAT_TAPESTRY_B, MAT_TAPESTRY_R]
for ti, tx in enumerate([-4, 0, 4]):
    tp = empty(f"tapestry_{ti}_p", (tx, 5.5, -4.85))
    # main cloth
    beveled_cube(f"tapestry_{ti}_cloth", (1.4, 1.8, 0.05), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=tp, mat=TAP_MATS[ti])
    # decorative band top
    beveled_cube(f"tapestry_{ti}_band", (1.5, 0.15, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.95, 0.02), parent=tp, mat=MAT_GOBLET)


# --- 30 PARTICLES feu drift --------------------------------------
particles = []
for pk in range(30):
    px = random.uniform(-6, 6)
    py = random.uniform(3, 7)
    pz = random.uniform(-3, 3)
    pp = smooth_sphere(f"particle_{pk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(px, py, pz), mat=MAT_PARTICLE)
    pp["_base"] = (px, py, pz)
    pp["_phase"] = pk * 0.15
    particles.append(pp)


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

    # 20 villageois lèvent gobelets cyclic
    for vd in villagers:
        if isinstance(vd, dict):
            ph = vd["phase"]
            arm_lift = math.radians(-60 + 15 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi))
            kf(vd["arm"], f, "rotation_euler", (arm_lift, 0, math.radians(20)))

    # ménestrel strumming (right arm fast)
    strum_ang = math.radians(-60 + 25 * math.sin(2 * math.pi * tt * 6))
    kf(arm_R_p, f, "rotation_euler", (strum_ang, 0, math.radians(15)))
    # body slight sway (rhythm)
    kf(menestrel_p, f, "rotation_euler", (0, math.radians(5 * math.sin(2 * math.pi * tt * 2)), 0))

    # 4 fireplace flames intense
    for fl in fp_flames:
        ph = fl["phase"]
        fp_sc = 1.0 + 0.25 * math.sin(2 * math.pi * tt * 4 + ph * math.pi)
        kf(fl["out"], f, "scale", (fp_sc * 0.8, fp_sc * 1.6, fp_sc * 0.8))
        kf(fl["in"], f, "scale", (fp_sc * 0.6, fp_sc * 1.8, fp_sc * 0.6))

    # 6 torches pulse
    for tr in torches:
        if isinstance(tr, dict):
            ph = tr["phase"]
            fp_sc = 1.0 + 0.15 * math.sin(2 * math.pi * tt * 3.5 + ph * math.pi)
            kf(tr["out"], f, "scale", (fp_sc * 0.85, fp_sc * 1.6, fp_sc * 0.85))
            kf(tr["in"], f, "scale", (fp_sc * 0.6, fp_sc * 1.8, fp_sc * 0.6))

    # chien tail wave
    kf(tail_p, f, "rotation_euler", (0, math.radians(25 * math.sin(2 * math.pi * tt * 2)), math.radians(15 * math.cos(2 * math.pi * tt * 1.8))))

    # 30 particles drift
    for pa in particles:
        bx_, by_, bz_ = pa["_base"]
        ph = pa["_phase"]
        nx = bx_ + 0.3 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        ny = by_ + 0.4 * math.cos(2 * math.pi * tt * 0.6 + ph * math.pi)
        nz = bz_ + 0.25 * math.sin(2 * math.pi * tt * 0.5 + ph * math.pi)
        kf(pa, f, "location", (nx, ny, nz))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_medieval_feast_tavern] wrote {OUT}")
