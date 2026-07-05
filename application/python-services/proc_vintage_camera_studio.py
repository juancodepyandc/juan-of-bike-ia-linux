"""
proc_vintage_camera_studio.py — 163e procédural AuroraIA, Phase F++++.
QUALITÉ ULTRA — feedback utilisateur appliqué (smooth + bevels + multi-axes).

Studio de photographe vintage avec appareil photo grand format soufflet :
- appareil photo grand format soufflet (boîtier + soufflet 8 plis + objectif + visée capot)
- trépied bois 3 jambes
- table accessoires
- 8 plaques photographiques verre encadrées
- 4 bouteilles produits chimiques émissives
- chiffon noir cape
- éclair magnesium émissif
- décor portrait : fauteuil + colonne + plante verte + tapis + tableau
- 20 photos sépia épinglées sur mur
- horloge ronde
- lampes éclairage 2 boîtes diffuseurs émissifs
- chambre noire arrière (rideau rouge émissif)
- 3 ampoules suspendues émissives
- particules poussière flottante émissives
- bottle d'encre + plume

Animations multi-axes simultanées :
- caméra : soufflet pulse expand/contract + objectif zoom in/out
- éclair magnesium : flash pulse intense cyclique
- 2 lampes éclairage : pulse différentielles
- 20 particules poussière : drift 3D
- 4 bouteilles chimiques : liquides slosh
- horloge : 2 aiguilles rotation
- 3 ampoules suspendues : pulse + sway
- rideau chambre noire : ondule

Sortie : output/3d/pbr_vintagecam_proc.glb.
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
OUT = os.path.normpath(os.path.join(CWD, "..", "output", "3d", "pbr_vintagecam_proc.glb"))

random.seed(0xCAFE5A)


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
MAT_WALL = make_mat("wall", (0.45, 0.30, 0.20), roughness=0.85, emi=(0.18, 0.12, 0.08), emi_strength=0.3)
MAT_WALL_DARK = make_mat("wall_dark", (0.25, 0.18, 0.12), roughness=0.90)
MAT_FLOOR = make_mat("floor", (0.30, 0.20, 0.12), roughness=0.85)
MAT_WOOD = make_mat("wood", (0.40, 0.25, 0.12), roughness=0.7)
MAT_WOOD_DARK = make_mat("wood_dark", (0.20, 0.12, 0.06), roughness=0.85)
MAT_BRASS = make_mat("brass", (0.85, 0.65, 0.30), metallic=0.9, roughness=0.25, emi=(0.30, 0.22, 0.12), emi_strength=0.4)
MAT_IRON = make_mat("iron", (0.40, 0.35, 0.30), metallic=0.8, roughness=0.50)
MAT_LEATHER = make_mat("leather", (0.18, 0.10, 0.05), roughness=0.85)
MAT_BELLOWS = make_mat("bellows", (0.15, 0.10, 0.06), roughness=0.85)
MAT_LENS_GLASS = make_mat("lens", (0.65, 0.85, 0.95), roughness=0.05, alpha=0.55, emi=(0.40, 0.55, 0.65), emi_strength=2.0)
MAT_LENS_DARK = make_mat("lens_dark", (0.10, 0.10, 0.12), roughness=0.20)
MAT_GLASS_PLATE = make_mat("glass_plate", (0.85, 0.90, 0.95), roughness=0.10, alpha=0.50, emi=(0.40, 0.45, 0.50), emi_strength=1.0)
MAT_PLATE_FRAME = make_mat("plate_frame", (0.55, 0.40, 0.25), roughness=0.6)
MAT_CHEM_R = make_mat("chem_red", (0.95, 0.30, 0.30), roughness=0.10, alpha=0.85, emi=(0.95, 0.30, 0.30), emi_strength=6.0)
MAT_CHEM_G = make_mat("chem_green", (0.30, 0.95, 0.40), roughness=0.10, alpha=0.85, emi=(0.30, 0.95, 0.40), emi_strength=6.0)
MAT_CHEM_B = make_mat("chem_blue", (0.30, 0.55, 0.95), roughness=0.10, alpha=0.85, emi=(0.30, 0.55, 0.95), emi_strength=6.0)
MAT_CHEM_Y = make_mat("chem_yellow", (0.95, 0.85, 0.20), roughness=0.10, alpha=0.85, emi=(0.95, 0.85, 0.20), emi_strength=6.0)
MAT_CHEM_BOTTLE = make_mat("chem_bottle", (0.85, 0.90, 0.95), roughness=0.20, alpha=0.55, emi=(0.30, 0.35, 0.40), emi_strength=0.8)
MAT_FLASH = make_mat("flash", (1.0, 1.0, 0.95), roughness=0.0, emi=(1.0, 1.0, 0.95), emi_strength=20.0)
MAT_FLASH_BOX = make_mat("flash_box", (0.50, 0.45, 0.40), metallic=0.5, roughness=0.45)
MAT_LIGHT_BOX = make_mat("light_box", (0.85, 0.80, 0.75), roughness=0.6, emi=(0.50, 0.45, 0.40), emi_strength=2.0)
MAT_LIGHT_CORE = make_mat("light_core", (1.0, 0.95, 0.75), roughness=0.0, emi=(1.0, 0.95, 0.75), emi_strength=14.0)
MAT_CHAIR_FAB = make_mat("chair_fabric", (0.55, 0.20, 0.20), roughness=0.7, emi=(0.20, 0.05, 0.05), emi_strength=0.3)
MAT_CHAIR_WOOD = make_mat("chair_wood", (0.30, 0.18, 0.08), roughness=0.7)
MAT_COLUMN = make_mat("column", (0.85, 0.82, 0.75), roughness=0.55)
MAT_PLANT_LEAF = make_mat("plant_leaf", (0.20, 0.55, 0.25), roughness=0.6, emi=(0.08, 0.20, 0.10), emi_strength=0.3)
MAT_PLANT_STEM = make_mat("plant_stem", (0.20, 0.50, 0.15), roughness=0.7)
MAT_PLANT_POT = make_mat("plant_pot", (0.55, 0.30, 0.20), roughness=0.7)
MAT_CARPET = make_mat("carpet", (0.45, 0.20, 0.18), roughness=0.85, emi=(0.18, 0.05, 0.05), emi_strength=0.3)
MAT_PHOTO_SEPIA = make_mat("photo_sepia", (0.85, 0.65, 0.40), roughness=0.6, emi=(0.40, 0.30, 0.18), emi_strength=0.5)
MAT_PHOTO_FRAME = make_mat("photo_frame", (0.40, 0.25, 0.10), roughness=0.7)
MAT_CLOCK_FACE = make_mat("clock_face", (0.92, 0.85, 0.65), roughness=0.40, emi=(0.35, 0.30, 0.20), emi_strength=0.6)
MAT_CLOCK_HAND = make_mat("clock_hand", (0.15, 0.10, 0.08), metallic=0.50, roughness=0.40)
MAT_BULB_FILAMENT = make_mat("bulb_fil", (1.0, 0.65, 0.20), roughness=0.0, emi=(1.0, 0.65, 0.20), emi_strength=12.0)
MAT_BULB_GLASS = make_mat("bulb_glass", (1.0, 0.90, 0.65), roughness=0.10, alpha=0.45, emi=(1.0, 0.80, 0.40), emi_strength=2.5)
MAT_CURTAIN = make_mat("curtain_red", (0.85, 0.15, 0.10), roughness=0.7, emi=(0.45, 0.05, 0.05), emi_strength=1.2)
MAT_DUST = make_mat("dust", (0.95, 0.92, 0.85), roughness=0.0, emi=(0.95, 0.92, 0.85), emi_strength=5.0)
MAT_INK = make_mat("ink", (0.05, 0.05, 0.10), roughness=0.4)
MAT_PAPER = make_mat("paper", (0.92, 0.88, 0.78), roughness=0.7, emi=(0.35, 0.32, 0.25), emi_strength=0.4)
MAT_TAPE = make_mat("table_dark", (0.30, 0.20, 0.12), roughness=0.7)


# --- backdrop : studio wall + floor ----------------------------------------
back_wall = beveled_cube("back_wall", (16, 0.2, 9), bevel_offset=0.05, bevel_segments=2, loc=(0, 4.5, 5), mat=MAT_WALL)
side_wall = beveled_cube("side_wall", (0.2, 9, 16), bevel_offset=0.05, bevel_segments=2, loc=(-8, 4.5, 0), mat=MAT_WALL_DARK)
floor = beveled_cube("floor", (16, 0.1, 12), bevel_offset=0.05, bevel_segments=2, loc=(0, -0.05, 0), mat=MAT_FLOOR)
# carpet
beveled_cube("carpet", (5, 0.05, 4), bevel_offset=0.04, bevel_segments=2, loc=(2, 0.02, 1), mat=MAT_CARPET)

# darkroom curtain rear (alpha overlay)
curtain_p = empty("curtain_p", (6, 2.5, 4.8))
curtain = beveled_cube("curtain", (3, 5, 0.05), bevel_offset=0.05, bevel_segments=2, loc=(0, 0, 0), parent=curtain_p, mat=MAT_CURTAIN)


# --- VINTAGE CAMERA ON TRIPOD (large format with bellows) -----------------
camera_p = empty("camera_p", (-2, 0, 2))

# tripod : 3 legs splay outward
tripod_top_y = 1.6
for tk in range(3):
    ta = tk * (math.pi * 2 / 3) + math.pi / 6
    leg_p = empty(f"tripod_leg_p_{tk}", (0, 0, 0), parent=camera_p)
    leg_p.rotation_euler = (math.radians(25 * math.cos(ta)), 0, math.radians(25 * math.sin(ta)))
    leg = smooth_cone(f"tripod_leg_{tk}", r1=0.05, r2=0.04, depth=1.6, segs=8, loc=(0, 0.80, 0), parent=leg_p, mat=MAT_WOOD_DARK)
    # foot
    smooth_sphere(f"tripod_foot_{tk}", r=0.07, segs=12, rings=8, loc=(math.cos(ta) * 0.35, 0.05, math.sin(ta) * 0.35), parent=camera_p, mat=MAT_IRON)
# top mount
smooth_cone("tripod_mount", r1=0.20, r2=0.18, depth=0.10, segs=14, loc=(0, tripod_top_y + 0.05, 0), parent=camera_p, mat=MAT_BRASS)

# main camera body (wooden box at front)
camera_body_p = empty("camera_body_p", (0, tripod_top_y + 0.30, 0), parent=camera_p)
body_front = beveled_cube("cam_body_front", (0.45, 0.45, 0.45), bevel_offset=0.04, bevel_segments=2, loc=(0.45, 0, 0), parent=camera_body_p, mat=MAT_WOOD)
# rear box (where film plate goes)
body_rear = beveled_cube("cam_body_rear", (0.50, 0.50, 0.50), bevel_offset=0.04, bevel_segments=2, loc=(-0.50, 0, 0), parent=camera_body_p, mat=MAT_WOOD)

# BELLOWS (8 segments expanding-contracting)
bellows_segs = []
for bs in range(8):
    bx = -0.20 + bs * 0.10
    # size varies (smaller in middle)
    sx = 0.40 - abs(bs - 3.5) * 0.02
    sy = 0.40 - abs(bs - 3.5) * 0.02
    bel = beveled_cube(f"bellows_{bs}", (0.10, sx, sy), bevel_offset=0.03, bevel_segments=2, loc=(bx, 0, 0), parent=camera_body_p, mat=MAT_BELLOWS)
    bellows_segs.append(bel)

# objectif (front lens assembly)
lens_p = empty("lens_p", (0.70, 0, 0), parent=camera_body_p)
# lens housing
smooth_cone("lens_housing", r1=0.16, r2=0.14, depth=0.18, segs=18, loc=(0.10, 0, 0), parent=lens_p, mat=MAT_BRASS)
lens_p_objects = bpy.data.objects.get("lens_housing")
if lens_p_objects:
    lens_p_objects.rotation_euler = (0, 0, math.radians(90))
# lens glass
smooth_sphere("lens_glass", r=0.13, segs=20, rings=14, loc=(0.18, 0, 0), parent=lens_p, mat=MAT_LENS_GLASS, scale=(0.4, 1.0, 1.0))
# aperture rings
for ar in range(3):
    arx = -0.10 + ar * 0.08
    ring = smooth_cone(f"lens_ring_{ar}", r1=0.17 + ar * 0.005, r2=0.17 + ar * 0.005, depth=0.04, segs=18, loc=(arx, 0, 0), parent=lens_p, mat=MAT_BRASS)
    ring.rotation_euler = (0, 0, math.radians(90))

# view hood (top of camera)
hood_p = empty("hood_p", (-0.50, 0.35, 0), parent=camera_body_p)
smooth_cone("hood_top", r1=0.20, r2=0.30, depth=0.30, segs=10, loc=(0, 0.15, 0), parent=hood_p, mat=MAT_LEATHER)

# black cloth cape draped on top
cape_p = empty("cape_p", (-0.40, 0.55, 0), parent=camera_body_p)
beveled_cube("cape", (0.85, 0.05, 0.85), bevel_offset=0.03, bevel_segments=2, loc=(0, 0, 0), parent=cape_p, mat=MAT_LEATHER)


# --- table accessoires (right side) ---------------------------------------
table_p = empty("table_p", (4, 0, 2))
# table top
beveled_cube("table_top", (2.0, 0.08, 1.2), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.0, 0), parent=table_p, mat=MAT_WOOD)
# 4 legs
for lx, lz in [(-0.85, -0.50), (0.85, -0.50), (-0.85, 0.50), (0.85, 0.50)]:
    smooth_cone(f"table_leg_{lx}_{lz}", r1=0.06, r2=0.05, depth=1.0, segs=8, loc=(lx, 0.50, lz), parent=table_p, mat=MAT_WOOD_DARK)

# 4 chemical bottles on table
chem_mats = [MAT_CHEM_R, MAT_CHEM_G, MAT_CHEM_B, MAT_CHEM_Y]
chem_bottles = []
for ck in range(4):
    cx = -0.7 + ck * 0.45
    cp = empty(f"chem_{ck}_p", (cx, 1.04, 0), parent=table_p)
    # bottle (cylinder + neck)
    smooth_cone(f"chem_{ck}_body", r1=0.10, r2=0.10, depth=0.30, segs=14, loc=(0, 0.15, 0), parent=cp, mat=MAT_CHEM_BOTTLE)
    # liquid inside
    smooth_cone(f"chem_{ck}_liq", r1=0.08, r2=0.08, depth=0.20, segs=12, loc=(0, 0.10, 0), parent=cp, mat=chem_mats[ck])
    # neck
    smooth_cone(f"chem_{ck}_neck", r1=0.05, r2=0.04, depth=0.08, segs=10, loc=(0, 0.34, 0), parent=cp, mat=MAT_CHEM_BOTTLE)
    # cork
    smooth_cone(f"chem_{ck}_cork", r1=0.05, r2=0.05, depth=0.04, segs=8, loc=(0, 0.40, 0), parent=cp, mat=MAT_WOOD_DARK)
    chem_bottles.append({"p": cp, "liq_mat": chem_mats[ck], "phase": ck * 0.30})

# 8 glass plates (in rack on table)
for pk in range(8):
    px = -0.50 + pk * 0.15
    plate_p = empty(f"plate_{pk}_p", (px, 1.30, 0.4), parent=table_p)
    # frame
    beveled_cube(f"plate_{pk}_frame", (0.10, 0.40, 0.30), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=plate_p, mat=MAT_PLATE_FRAME)
    # plate
    beveled_cube(f"plate_{pk}_glass", (0.04, 0.32, 0.22), bevel_offset=0.01, bevel_segments=2, loc=(0.05, 0, 0), parent=plate_p, mat=MAT_GLASS_PLATE)
    plate_p.rotation_euler = (0, 0, math.radians(80))

# ink bottle + plume
ink_p = empty("ink_p", (-0.85, 1.04, -0.4), parent=table_p)
smooth_cone("ink_bottle", r1=0.07, r2=0.06, depth=0.10, segs=10, loc=(0, 0.05, 0), parent=ink_p, mat=MAT_INK)
# plume
feather_p = empty("feather_p", (0, 0.10, 0), parent=ink_p)
feather_shaft = smooth_cone("feather_shaft", r1=0.012, r2=0.008, depth=0.40, segs=6, loc=(0, 0.25, 0), parent=feather_p, mat=MAT_LEATHER)
feather_shaft.rotation_euler = (0, 0, math.radians(20))
for fb in range(5):
    smooth_sphere(f"feather_fan_{fb}", r=0.04, segs=10, rings=6, loc=(0.05, 0.30 + fb * 0.04, 0), parent=feather_p, mat=MAT_LEATHER, scale=(1.0, 1.0, 0.2))

# paper sheet
beveled_cube("paper", (0.30, 0.01, 0.40), bevel_offset=0.01, bevel_segments=2, loc=(0.7, 1.05, -0.3), parent=table_p, mat=MAT_PAPER)


# --- éclair magnesium (flashbulb on stand) -------------------------------
flash_p = empty("flash_p", (4.5, 1.2, -0.5))
# stand
smooth_cone("flash_stand", r1=0.04, r2=0.04, depth=1.0, segs=8, loc=(0, -0.5, 0), parent=flash_p, mat=MAT_IRON)
# tray base
smooth_cone("flash_tray", r1=0.20, r2=0.18, depth=0.05, segs=14, loc=(0, 0.05, 0), parent=flash_p, mat=MAT_FLASH_BOX)
# magnesium powder pile
smooth_sphere("flash_powder", r=0.12, segs=14, rings=10, loc=(0, 0.10, 0), parent=flash_p, mat=MAT_FLASH_BOX, scale=(1.0, 0.50, 1.0))
# flash glow (animated)
flash_glow = smooth_sphere("flash_glow", r=0.20, segs=16, rings=12, loc=(0, 0.10, 0), parent=flash_p, mat=MAT_FLASH, scale=(1.0, 0.6, 1.0))


# --- 2 lampes éclairage softbox ------------------------------------------
lights_set = []
for lk in range(2):
    lx = -5 + lk * 8
    lp = empty(f"light_{lk}_p", (lx, 2.5, -1.0))
    # stand
    smooth_cone(f"light_{lk}_stand", r1=0.04, r2=0.04, depth=2.5, segs=8, loc=(0, -1.25, 0), parent=lp, mat=MAT_IRON)
    # softbox
    sbox = beveled_cube(f"light_{lk}_box", (0.55, 0.55, 0.55), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=lp, mat=MAT_LIGHT_BOX)
    sbox.rotation_euler = (0, math.radians(-30 if lk == 0 else 30), 0)
    # glow front
    glow = smooth_sphere(f"light_{lk}_glow", r=0.30, segs=18, rings=12, loc=(0, 0, 0.30), parent=sbox, mat=MAT_LIGHT_CORE, scale=(1.0, 1.0, 0.30))
    lights_set.append({"p": lp, "glow": glow, "phase": lk * 0.5})


# --- portrait setup : fauteuil + colonne + plante + tableau --------------
# fauteuil victorien
chair_p = empty("chair_p", (0.8, 0, -0.5))
# seat
beveled_cube("chair_seat", (0.65, 0.10, 0.55), bevel_offset=0.04, bevel_segments=2, loc=(0, 0.65, 0), parent=chair_p, mat=MAT_CHAIR_FAB)
# back
beveled_cube("chair_back", (0.65, 1.0, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(0, 1.20, -0.25), parent=chair_p, mat=MAT_CHAIR_FAB)
# 4 legs
for lx, lz in [(-0.25, -0.20), (0.25, -0.20), (-0.25, 0.20), (0.25, 0.20)]:
    smooth_cone(f"chair_leg_{lx}_{lz}", r1=0.05, r2=0.04, depth=0.65, segs=8, loc=(lx, 0.30, lz), parent=chair_p, mat=MAT_CHAIR_WOOD)
# armrests
for ay in [0.30, -0.30]:
    beveled_cube(f"chair_arm_{ay}", (0.55, 0.06, 0.06), bevel_offset=0.02, bevel_segments=2, loc=(0, 0.95, ay), parent=chair_p, mat=MAT_CHAIR_WOOD)
# decorative top knobs
for kx in [-0.30, 0.30]:
    smooth_sphere(f"chair_knob_{kx}", r=0.06, segs=12, rings=8, loc=(kx, 1.75, -0.25), parent=chair_p, mat=MAT_BRASS)

# colonne décorative (gauche du fauteuil)
column_p = empty("column_p", (-0.5, 0, -0.5))
# base
smooth_cone("column_base", r1=0.30, r2=0.25, depth=0.20, segs=14, loc=(0, 0.10, 0), parent=column_p, mat=MAT_COLUMN)
# shaft
smooth_cone("column_shaft", r1=0.20, r2=0.18, depth=1.5, segs=14, loc=(0, 0.95, 0), parent=column_p, mat=MAT_COLUMN)
# capital
smooth_cone("column_cap", r1=0.25, r2=0.22, depth=0.12, segs=14, loc=(0, 1.76, 0), parent=column_p, mat=MAT_COLUMN)
# vase on top
smooth_sphere("column_vase", r=0.20, segs=18, rings=14, loc=(0, 2.0, 0), parent=column_p, mat=MAT_PLANT_POT, scale=(1.0, 0.85, 1.0))

# plante verte
plant_p = empty("plant_p", (0, 2.10, 0), parent=column_p)
# leaves cluster
for lk in range(8):
    la = lk * (math.pi * 2 / 8)
    lh = random.uniform(0.30, 0.45)
    leaf_p = empty(f"plant_leaf_p_{lk}", (math.cos(la) * 0.10, 0.1, math.sin(la) * 0.10), parent=plant_p)
    leaf_p.rotation_euler = (0, -la, math.radians(-35))
    smooth_sphere(f"plant_leaf_{lk}", r=0.08, segs=12, rings=8, loc=(0.20, lh, 0), parent=leaf_p, mat=MAT_PLANT_LEAF, scale=(1.5, 0.10, 0.6))

# tableau sur mur arrière
frame_p = empty("frame_p", (3, 4, 4.9))
beveled_cube("frame_outer", (1.4, 1.7, 0.10), bevel_offset=0.04, bevel_segments=2, loc=(0, 0, 0), parent=frame_p, mat=MAT_PHOTO_FRAME)
beveled_cube("frame_pic", (1.2, 1.5, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0.06), parent=frame_p, mat=MAT_PHOTO_SEPIA)


# --- 20 photos sépia épinglées sur mur (arrière-plan) -------------------
for ph in range(20):
    px = -7 + (ph % 5) * 1.5
    py = 6 + (ph // 5) * 0.55
    photo_p = empty(f"photo_{ph}_p", (px, py, 4.85))
    photo_p.rotation_euler = (0, 0, math.radians(random.uniform(-8, 8)))
    # frame
    beveled_cube(f"photo_{ph}_fr", (0.35, 0.45, 0.04), bevel_offset=0.02, bevel_segments=2, loc=(0, 0, 0), parent=photo_p, mat=MAT_PHOTO_FRAME)
    # photo image
    beveled_cube(f"photo_{ph}_im", (0.30, 0.40, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(0, 0, 0.04), parent=photo_p, mat=MAT_PHOTO_SEPIA)


# --- horloge ronde sur mur ----------------------------------------------
clock_p = empty("clock_p", (-3.5, 5, 4.9))
# face
smooth_cone("clock_face_b", r1=0.50, r2=0.48, depth=0.10, segs=24, loc=(0, 0, 0), parent=clock_p, mat=MAT_BRASS)
# face inner
smooth_cone("clock_face_in", r1=0.45, r2=0.45, depth=0.05, segs=24, loc=(0, 0, 0.07), parent=clock_p, mat=MAT_CLOCK_FACE)
# 12 numerals
for n in range(12):
    na = -math.pi / 2 + n * (math.pi * 2 / 12)
    nx = math.cos(na) * 0.36
    ny = math.sin(na) * 0.36
    beveled_cube(f"clock_n_{n}", (0.05, 0.08, 0.02), bevel_offset=0.01, bevel_segments=2, loc=(nx, ny, 0.10), parent=clock_p, mat=MAT_CLOCK_HAND)
# hour hand
hour_p = empty("clock_hour_p", (0, 0, 0.12), parent=clock_p)
beveled_cube("clock_hour", (0.05, 0.25, 0.025), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.08, 0), parent=hour_p, mat=MAT_CLOCK_HAND)
# minute hand
minute_p = empty("clock_minute_p", (0, 0, 0.13), parent=clock_p)
beveled_cube("clock_minute", (0.035, 0.38, 0.025), bevel_offset=0.01, bevel_segments=2, loc=(0, 0.16, 0), parent=minute_p, mat=MAT_CLOCK_HAND)
# center
smooth_sphere("clock_center", r=0.05, segs=12, rings=8, loc=(0, 0, 0.14), parent=clock_p, mat=MAT_BRASS)


# --- 3 ampoules suspendues -----------------------------------------------
bulbs = []
for bk in range(3):
    bx = -3 + bk * 3
    bulb_p = empty(f"bulb_p_{bk}", (bx, 6.5, 1))
    # chain
    smooth_cone(f"bulb_{bk}_chain", r1=0.02, r2=0.02, depth=2.0, segs=4, loc=(0, 0.9, 0), parent=bulb_p, mat=MAT_IRON)
    # glass
    smooth_sphere(f"bulb_{bk}_glass", r=0.20, segs=16, rings=12, loc=(0, -0.20, 0), parent=bulb_p, mat=MAT_BULB_GLASS, scale=(1.0, 1.3, 1.0))
    # filament
    fil = smooth_sphere(f"bulb_{bk}_fil", r=0.08, segs=12, rings=8, loc=(0, -0.20, 0), parent=bulb_p, mat=MAT_BULB_FILAMENT)
    # socket
    smooth_cone(f"bulb_{bk}_socket", r1=0.10, r2=0.09, depth=0.10, segs=10, loc=(0, 0, 0), parent=bulb_p, mat=MAT_IRON)
    bulbs.append({"p": bulb_p, "fil": fil, "phase": bk * 0.5})


# --- 40 particules poussière -------------------------------------------
dust_parts = []
for dk in range(40):
    dx = random.uniform(-6, 6)
    dy = random.uniform(1, 7)
    dz = random.uniform(-1, 4)
    dp = smooth_sphere(f"dust_{dk}", r=random.uniform(0.025, 0.05), segs=8, rings=6, loc=(dx, dy, dz), mat=MAT_DUST)
    dp["_base"] = (dx, dy, dz)
    dp["_phase"] = dk * 0.18
    dust_parts.append(dp)


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

    # camera bellows : expand-contract pulse (8 segments scale modulation)
    for bs in bellows_segs:
        bx_loc = bs.location.x
        # subtle scale Y+Z
        scl = 1.0 + 0.10 * math.sin(2 * math.pi * tt * 1.5)
        kf(bs, f, "scale", (1.0, scl, scl))

    # camera body slight bob (focus adjustment)
    cb_bob = math.sin(2 * math.pi * tt * 1.2) * 0.04
    kf(camera_body_p, f, "rotation_euler", (math.radians(2 * cb_bob), 0, 0))

    # flash : pulse intense intermittent (peaks every 1.5s)
    flash_pulse = math.exp(-((tt % 0.25) * 12)) if (tt % 0.25) < 0.10 else 0.2
    fp = 1.0 + flash_pulse * 4.0
    kf(flash_glow, f, "scale", (fp, fp * 0.6, fp))

    # 2 lamps softbox : pulse différentielles (subtle warm flicker)
    for ld in lights_set:
        ph = ld["phase"]
        gs = 1.0 + 0.05 * math.sin(2 * math.pi * tt * 1.8 + ph * math.pi)
        kf(ld["glow"], f, "scale", (gs, gs, gs * 0.30))

    # 4 chemical bottles : liquid slosh (rotation slight)
    for cd in chem_bottles:
        ph = cd["phase"]
        # liquid level slight rotation
        kf(cd["p"], f, "rotation_euler", (math.radians(2 * math.sin(2 * math.pi * tt * 1.5 + ph * math.pi)), 0, math.radians(2 * math.cos(2 * math.pi * tt * 1.7 + ph * math.pi))))

    # 40 dust particles drift 3D
    for dp in dust_parts:
        bx_, by_, bz_ = dp["_base"]
        ph = dp["_phase"]
        nx = bx_ + 0.3 * math.sin(2 * math.pi * tt * 0.7 + ph * math.pi)
        ny = by_ + 0.4 * math.cos(2 * math.pi * tt * 0.5 + ph * math.pi)
        nz = bz_ + 0.25 * math.sin(2 * math.pi * tt * 0.6 + ph * math.pi)
        kf(dp, f, "location", (nx, ny, nz))
        sc = 0.6 + 0.6 * abs(math.sin(2 * math.pi * tt * 3 + ph * math.pi))
        kf(dp, f, "scale", (sc, sc, sc))

    # clock hands rotation
    hour_ang = tt * 2 * math.pi * 1.0
    minute_ang = tt * 2 * math.pi * 12.0
    kf(hour_p, f, "rotation_euler", (0, 0, -hour_ang))
    kf(minute_p, f, "rotation_euler", (0, 0, -minute_ang))

    # 3 bulbs pulse + sway
    for bd in bulbs:
        ph = bd["phase"]
        ps = 1.0 + 0.12 * math.sin(2 * math.pi * tt * 3.5 + ph * math.pi)
        kf(bd["fil"], f, "scale", (ps, ps, ps))
        # sway X
        sway = math.radians(4 * math.sin(2 * math.pi * tt * 0.8 + ph * math.pi))
        kf(bd["p"], f, "rotation_euler", (sway, 0, math.radians(3 * math.cos(2 * math.pi * tt * 0.9 + ph * math.pi))))

    # curtain : ondule
    curtain_wave = math.radians(3 * math.sin(2 * math.pi * tt * 1.2))
    kf(curtain_p, f, "rotation_euler", (curtain_wave, 0, math.radians(2 * math.cos(2 * math.pi * tt * 1.5))))


scene.frame_set(1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=True, export_apply=False)
print(f"[proc_vintage_camera_studio] wrote {OUT}")
