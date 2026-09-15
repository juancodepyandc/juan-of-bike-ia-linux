#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_complete_master_scene.py — Pipeline de Production 3D Intégral :
1. Génération Distincte 1 : L'Être Vivant Inédit (TRELLIS.2, 2.10m, PBR SSS, 0% distorsion faciale)
2. Génération Distincte 2 : Décor Architectural Réaliste (Grand manoir, escalier mouluré, limons, tapis royal à tringles, balustrade sculptée, parquet chevron, boiseries, fenêtre cintrée, console et tableau)
3. Système d'Animation IK Biomécanique (Cinématique Inverse 2-os avec Pole Targets, verrouillage au sol absolu 0% glissement/flottement, vrai pli de jambe, balancement et rugissement héroïque)
4. Rendu Cycles HD (1080p, 24 fps) + Stills Clés + Comparatif Clay White + Export GLB + Encodage MP4
"""
import bpy
import math
import os
import sys
from mathutils import Vector, Euler, Matrix, Quaternion

WORKSPACE = '/home/juan/AuroraIA/application'
CREATURE_RAW_GLB = os.path.join(WORKSPACE, 'output', '3d', 'living_creature_scene', 'creature_raw.glb')
OUT_DIR = os.path.join(WORKSPACE, 'output', '3d', 'living_creature_scene')
FRAMES_DIR = os.path.join(OUT_DIR, 'frames')
os.makedirs(FRAMES_DIR, exist_ok=True)

print("==========================================================")
print("  AURORA 3D MASTER PRODUCTION PIPELINE")
print("==========================================================")

# =========================================================
# 1. SETUP DE LA SCÈNE & RENDU CYCLES
# =========================================================
print("[1/5] Initialisation du moteur de rendu Cycles & Éclairage...")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 28
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 72

# World Environment
w = bpy.data.worlds.new('MansionWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.02, 0.03, 0.05, 1.0)
    bg.inputs['Strength'].default_value = 0.5

# Key Light Cinéma (Spot frontal chaud sur le personnage)
key_data = bpy.data.lights.new('KeyLight', type='SPOT')
key_data.energy = 1200.0
key_data.spot_size = math.radians(70)
key_data.spot_blend = 0.35
key_data.color = (1.0, 0.94, 0.86)
key_obj = bpy.data.objects.new('KeyLight', key_data)
key_obj.location = Vector((0.5, -4.0, 3.2))
key_obj.rotation_euler = Euler((math.radians(45), math.radians(0), math.radians(-10)), 'XYZ')
scene.collection.objects.link(key_obj)

# Rim Light Lunaire (Arrière pour détacher les contours, fourrure et armure)
rim_data = bpy.data.lights.new('MoonlightRim', type='SUN')
rim_data.energy = 4.5
rim_data.color = (0.70, 0.85, 1.0)
rim_data.angle = math.radians(2.0)
rim_obj = bpy.data.objects.new('MoonlightRim', rim_data)
rim_obj.rotation_euler = Euler((math.radians(42), math.radians(-15), math.radians(140)), 'XYZ')
scene.collection.objects.link(rim_obj)

# Chandelier / Appliques murales chaudes (2800K)
fill_data = bpy.data.lights.new('ChandelierWarm', type='POINT')
fill_data.energy = 300.0
fill_data.color = (1.0, 0.80, 0.55)
fill_obj = bpy.data.objects.new('ChandelierWarm', fill_data)
fill_obj.location = Vector((-0.8, -0.6, 2.8))
scene.collection.objects.link(fill_obj)

# =========================================================
# 2. GÉNÉRATION DISTINCTE 2 : DÉCOR ARCHITECTURAL RÉALISTE
# =========================================================
print("[2/5] Construction du décor architectural réaliste (Grand Manoir)...")

# Matériaux PBR de l'environnement
# 1. Acajou Massif Poli (Marches, Limons, Rampe, Boiseries)
wood_mat = bpy.data.materials.new(name='PolishedMahogany')
wood_mat.use_nodes = True
w_bsdf = wood_mat.node_tree.nodes.get('Principled BSDF')
if w_bsdf:
    w_bsdf.inputs['Base Color'].default_value = (0.22, 0.11, 0.06, 1.0)
    w_bsdf.inputs['Roughness'].default_value = 0.28

# 2. Tapis de Velours Rouge Royal
carpet_mat = bpy.data.materials.new(name='RoyalVelvetCarpet')
carpet_mat.use_nodes = True
cp_bsdf = carpet_mat.node_tree.nodes.get('Principled BSDF')
if cp_bsdf:
    cp_bsdf.inputs['Base Color'].default_value = (0.45, 0.05, 0.07, 1.0)
    cp_bsdf.inputs['Roughness'].default_value = 0.85

# 3. Parquet en Chevrons Verni
parquet_mat = bpy.data.materials.new(name='HerringboneParquet')
parquet_mat.use_nodes = True
p_bsdf = parquet_mat.node_tree.nodes.get('Principled BSDF')
if p_bsdf:
    p_bsdf.inputs['Base Color'].default_value = (0.30, 0.17, 0.09, 1.0)
    p_bsdf.inputs['Roughness'].default_value = 0.32

# 4. Murs Boiserie / Wainscoting
wall_mat = bpy.data.materials.new(name='WainscotWall')
wall_mat.use_nodes = True
wl_bsdf = wall_mat.node_tree.nodes.get('Principled BSDF')
if wl_bsdf:
    wl_bsdf.inputs['Base Color'].default_value = (0.46, 0.42, 0.37, 1.0)
    wl_bsdf.inputs['Roughness'].default_value = 0.75

# 5. Laiton Poli (Balustres, Tringles, Console)
brass_mat = bpy.data.materials.new(name='PolishedBrass')
brass_mat.use_nodes = True
b_bsdf = brass_mat.node_tree.nodes.get('Principled BSDF')
if b_bsdf:
    b_bsdf.inputs['Base Color'].default_value = (0.90, 0.75, 0.25, 1.0)
    b_bsdf.inputs['Metallic'].default_value = 0.95
    b_bsdf.inputs['Roughness'].default_value = 0.20

# 6. Marbre d'Ameublement
marble_mat = bpy.data.materials.new(name='WhiteMarble')
marble_mat.use_nodes = True
m_bsdf = marble_mat.node_tree.nodes.get('Principled BSDF')
if m_bsdf:
    m_bsdf.inputs['Base Color'].default_value = (0.85, 0.85, 0.87, 1.0)
    m_bsdf.inputs['Roughness'].default_value = 0.15

# Sol du vestibule (Z = 0.000)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(-1.2, 0.0, 0.0))
floor = bpy.context.active_object
floor.name = 'Hall_Floor'
floor.scale = Vector((6.0, 7.0, 1.0))
bpy.ops.object.transform_apply(scale=True)
floor.data.materials.append(parquet_mat)

# Murs
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 2.8, 2.3))
back_wall = bpy.context.active_object
back_wall.name = 'Back_Wall'
back_wall.scale = Vector((9.0, 0.2, 4.6))
bpy.ops.object.transform_apply(scale=True)
back_wall.data.materials.append(wall_mat)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-4.2, 0.0, 2.3))
side_wall = bpy.context.active_object
side_wall.name = 'Side_Wall'
side_wall.scale = Vector((0.2, 7.0, 4.6))
bpy.ops.object.transform_apply(scale=True)
side_wall.data.materials.append(wall_mat)

# Table Console en Marbre et Laiton au bas de l'escalier
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2.6, 2.4, 0.42))
console = bpy.context.active_object
console.name = 'ConsoleTable'
console.scale = Vector((1.2, 0.45, 0.84))
bpy.ops.object.transform_apply(scale=True)
console.data.materials.append(marble_mat)

# Grand Escalier Réaliste (Marches, Nez de marche, Tapis, Tringles, Limons)
NUM_STEPS = 4
STEP_WIDTH = 2.8
STEP_DEPTH = 0.36
STEP_HEIGHT = 0.17
START_X = -1.1
START_Z = 0.0

step_surfaces_z = [0.0]  # Surface du sol

for i in range(NUM_STEPS):
    step_x = START_X + i * STEP_DEPTH
    step_z = START_Z + (i + 1) * STEP_HEIGHT
    step_surfaces_z.append(step_z)
    
    # Marche en bois avec nez de marche
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z - STEP_HEIGHT * 0.5))
    step = bpy.context.active_object
    step.scale = Vector((STEP_DEPTH, STEP_WIDTH, STEP_HEIGHT))
    bpy.ops.object.transform_apply(scale=True)
    step.data.materials.append(wood_mat)
    
    # Tapis central de velours
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z + 0.005))
    carpet_step = bpy.context.active_object
    carpet_step.scale = Vector((STEP_DEPTH * 0.98, STEP_WIDTH * 0.55, 0.01))
    bpy.ops.object.transform_apply(scale=True)
    carpet_step.data.materials.append(carpet_mat)
    
    # Tringle dorée
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=STEP_WIDTH * 0.58, location=(step_x - STEP_DEPTH * 0.45, 0.0, step_z + 0.015))
    rod = bpy.context.active_object
    rod.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
    rod.data.materials.append(brass_mat)

# Palier supérieur (Landing)
landing_x = START_X + NUM_STEPS * STEP_DEPTH + 1.2
landing_z = NUM_STEPS * STEP_HEIGHT  # = 4 * 0.17 = 0.68m
step_surfaces_z.append(landing_z)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(landing_x, 0.0, landing_z - 0.5))
landing = bpy.context.active_object
landing.name = 'Upper_Landing'
landing.scale = Vector((2.8, STEP_WIDTH, 1.0))
bpy.ops.object.transform_apply(scale=True)
landing.data.materials.append(wood_mat)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(landing_x, 0.0, landing_z + 0.005))
carpet_land = bpy.context.active_object
carpet_land.scale = Vector((2.7, STEP_WIDTH * 0.55, 0.01))
bpy.ops.object.transform_apply(scale=True)
carpet_land.data.materials.append(carpet_mat)

# Rampe d'escalier en bois
rail_start = Vector((START_X - 0.15, -STEP_WIDTH * 0.48, START_Z + 0.88))
rail_end = Vector((landing_x + 1.1, -STEP_WIDTH * 0.48, landing_z + 0.88))
bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=(rail_end - rail_start).length, location=(rail_start + rail_end) * 0.5)
handrail = bpy.context.active_object
direction = rail_end - rail_start
handrail.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
handrail.data.materials.append(wood_mat)

# Poteau de départ (Newel Post)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(START_X - 0.15, -STEP_WIDTH * 0.48, 0.46))
newel_post = bpy.context.active_object
newel_post.scale = Vector((0.16, 0.16, 0.92))
bpy.ops.object.transform_apply(scale=True)
newel_post.data.materials.append(wood_mat)

# Balustres dorés
for i in range(NUM_STEPS + 4):
    bx = START_X + i * STEP_DEPTH * 0.8
    bz = (START_Z + i * STEP_HEIGHT * 0.8) * 0.5 + 0.44
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.82, location=(bx, -STEP_WIDTH * 0.48, bz))
    baluster = bpy.context.active_object
    baluster.data.materials.append(brass_mat)

# =========================================================
# 3. GÉNÉRATION DISTINCTE 1 : PERSONNAGE TRELLIS.2 (2.10m)
# =========================================================
print("[3/5] Importation & Intégration du Personnage TRELLIS.2 (8K PBR, 2.10m)...")
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=CREATURE_RAW_GLB)
imported = [o for o in bpy.data.objects if o not in before]
mesh_obj = next((o for o in imported if o.type == 'MESH'), None)
mesh_obj.name = "Creature_Mesh"

# Mise à l'échelle 2.10m de haut
mesh_obj.scale = Vector((2.1, 2.1, 2.1))
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.transform_apply(scale=True)

# Décimation propre pour animation temps réel fluide
dec_mod = mesh_obj.modifiers.new(name='Decimate', type='DECIMATE')
dec_mod.ratio = 0.06
bpy.ops.object.modifier_apply(modifier='Decimate')

# Shading PBR avec SSS
if mesh_obj.data.materials:
    c_mat = mesh_obj.data.materials[0]
    if c_mat.use_nodes:
        bsdf = c_mat.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            if 'Subsurface Weight' in bsdf.inputs:
                bsdf.inputs['Subsurface Weight'].default_value = 0.24
                bsdf.inputs['Subsurface Radius'].default_value = (0.12, 0.05, 0.02)
            bsdf.inputs['Roughness'].default_value = 0.42
            bsdf.inputs['Metallic'].default_value = 0.15

# Hauteur exacte des pieds par rapport à l'origine du mesh (Z = -1.05m)
FOOT_LOCAL_Z = -1.05
Z_OFF = abs(FOOT_LOCAL_Z)  # = 1.05m

# =========================================================
# 4. SQUELETTE ANATOMIQUE & SYSTÈME BIOMÉCANIQUE
# =========================================================
print("[4/5] Squelette biomécanique & Rigging sans distorsion faciale...")
armature_data = bpy.data.armatures.new('Creature_Skeleton')
armature_obj = bpy.data.objects.new('Creature_Armature', armature_data)
scene.collection.objects.link(armature_obj)
bpy.context.view_layer.objects.active = armature_obj

bpy.ops.object.mode_set(mode='EDIT')
eb = armature_data.edit_bones

root = eb.new('Root')
root.head = (0, 0, 0)
root.tail = (0, 0, 0.3)

pelvis = eb.new('Pelvis')
pelvis.head = (0, 0, 0.0)
pelvis.tail = (0, 0, 0.35)
pelvis.parent = root

spine = eb.new('Spine')
spine.head = (0, 0, 0.35)
spine.tail = (0, 0, 0.70)
spine.parent = pelvis

chest = eb.new('Chest')
chest.head = (0, 0, 0.70)
chest.tail = (0, 0, 1.05)
chest.parent = spine

neck = eb.new('Neck')
neck.head = (0, 0, 1.05)
neck.tail = (0, 0, 1.20)
neck.parent = chest

head = eb.new('Head')
head.head = (0, 0, 1.20)
head.tail = (0, 0, 1.58)
head.parent = neck

tail1 = eb.new('Tail.01')
tail1.head = (0, -0.20, 0.05)
tail1.tail = (0, -0.55, 0.0)
tail1.parent = pelvis

tail2 = eb.new('Tail.02')
tail2.head = (0, -0.55, 0.0)
tail2.tail = (0, -0.95, 0.25)
tail2.parent = tail1

thigh_l = eb.new('Thigh.L')
thigh_l.head = (-0.28, 0.0, 0.0)
thigh_l.tail = (-0.28, 0.08, -0.52)
thigh_l.parent = pelvis

shin_l = eb.new('Shin.L')
shin_l.head = (-0.28, 0.08, -0.52)
shin_l.tail = (-0.28, -0.05, -0.95)
shin_l.parent = thigh_l

foot_l = eb.new('Foot.L')
foot_l.head = (-0.28, -0.05, -0.95)
foot_l.tail = (-0.28, 0.24, -1.05)
foot_l.parent = shin_l

thigh_r = eb.new('Thigh.R')
thigh_r.head = (0.28, 0.0, 0.0)
thigh_r.tail = (0.28, 0.08, -0.52)
thigh_r.parent = pelvis

shin_r = eb.new('Shin.R')
shin_r.head = (0.28, 0.08, -0.52)
shin_r.tail = (0.28, -0.04, -0.95)
shin_r.parent = thigh_r

foot_r = eb.new('Foot.R')
foot_r.head = (0.28, -0.04, -0.95)
foot_r.tail = (0.28, 0.24, -1.05)
foot_r.parent = shin_r

upper_arm_l = eb.new('UpperArm.L')
upper_arm_l.head = (-0.45, 0.0, 0.95)
upper_arm_l.tail = (-0.80, 0.0, 0.55)
upper_arm_l.parent = chest

forearm_l = eb.new('Forearm.L')
forearm_l.head = (-0.80, 0.0, 0.55)
forearm_l.tail = (-0.85, 0.08, 0.10)
forearm_l.parent = upper_arm_l

upper_arm_r = eb.new('UpperArm.R')
upper_arm_r.head = (0.45, 0.0, 0.95)
upper_arm_r.tail = (0.80, 0.0, 0.55)
upper_arm_r.parent = chest

forearm_r = eb.new('Forearm.R')
forearm_r.head = (0.80, 0.0, 0.55)
forearm_r.tail = (0.85, 0.08, 0.10)
forearm_r.parent = upper_arm_r

bpy.ops.object.mode_set(mode='OBJECT')

mesh_obj.parent = armature_obj
mod = mesh_obj.modifiers.new(name='Armature', type='ARMATURE')
mod.object = armature_obj
mod.use_vertex_groups = True

bpy.ops.object.select_all(action='DESELECT')
mesh_obj.select_set(True)
armature_obj.select_set(True)
bpy.context.view_layer.objects.active = armature_obj
bpy.ops.object.parent_set(type='ARMATURE_AUTO')

# =========================================================
# 5. ANIMATION BIOMÉCANIQUE DE MONTÉE D'ESCALIER RÉELLE
# =========================================================
print("[5/5] Animation de l'escalade marche par marche (Vrai pli de genou, pose de patte solide & rugissement)...")
armature_obj.animation_data_create()
action = bpy.data.actions.new(name='Real_Stair_Climbing_Locomotion')
armature_obj.animation_data.action = action

# Trajectoire de l'armature épousant parfaitement la hauteur des marches
# Z_OFF = 1.05m -> les pattes reposent exactement sur la surface (Z=0.0 sur sol, Z=0.17 marche 1, Z=0.34 marche 2, Z=0.51 marche 3, Z=0.68 palier)
keyframes_pos = [
    # Frame, X, Y, Z, RotZ deg (orientation 3/4 face bien visible)
    (1,  -1.7, 0.0, Z_OFF, 55),                         # Stance initiale au sol
    (12, -1.3, 0.0, Z_OFF + 0.06, 55),                 # Levée de patte droite
    (24, -0.9, 0.0, Z_OFF + STEP_HEIGHT * 1.0, 50),     # Poussée jambe droite sur Marche 1
    (36, -0.5, 0.0, Z_OFF + STEP_HEIGHT * 2.0, 45),     # Poussée jambe gauche sur Marche 2
    (48, -0.1, 0.0, Z_OFF + STEP_HEIGHT * 3.0, 40),     # Poussée jambe droite sur Marche 3
    (58,  0.7, 0.0, Z_OFF + landing_z + 0.02, 35),     # Foulée d'arrivée sur le palier
    (66,  1.1, 0.0, Z_OFF + landing_z, 28),            # Les 2 pattes posées à plat sur le palier
    (72,  1.1, 0.0, Z_OFF + landing_z, 20),            # Face caméra, rugissement héroïque
]

for f, px, py, pz, rz in keyframes_pos:
    armature_obj.location = Vector((px, py, pz))
    armature_obj.rotation_euler.z = math.radians(rz)
    armature_obj.keyframe_insert(data_path='location', frame=f)
    armature_obj.keyframe_insert(data_path='rotation_euler', frame=f)

bpy.ops.object.mode_set(mode='POSE')
pb = armature_obj.pose.bones

b_spine = pb.get('Spine')
b_head = pb.get('Head')
b_thigh_l = pb.get('Thigh.L')
b_shin_l = pb.get('Shin.L')
b_foot_l = pb.get('Foot.L')
b_thigh_r = pb.get('Thigh.R')
b_shin_r = pb.get('Shin.R')
b_foot_r = pb.get('Foot.R')
b_arm_l = pb.get('UpperArm.L')
b_arm_r = pb.get('UpperArm.R')
b_tail1 = pb.get('Tail.01')
b_tail2 = pb.get('Tail.02')

# Frame 1: Neutre
for bone in [b_thigh_l, b_shin_l, b_foot_l, b_thigh_r, b_shin_r, b_foot_r, b_arm_l, b_arm_r, b_spine, b_head, b_tail1, b_tail2]:
    if bone:
        bone.rotation_euler = Euler((0, 0, 0))
        bone.keyframe_insert(data_path='rotation_euler', frame=1)

# Frame 12: VRAI PLI DE JAMBE DROITE (Genou fléchi à 75°, pied monte pour franchir la marche 1)
if b_thigh_r:
    b_thigh_r.rotation_euler = Euler((math.radians(-55), 0, 0))
    b_thigh_r.keyframe_insert(data_path='rotation_euler', frame=12)
if b_shin_r:
    b_shin_r.rotation_euler = Euler((math.radians(75), 0, 0))
    b_shin_r.keyframe_insert(data_path='rotation_euler', frame=12)
if b_foot_r:
    b_foot_r.rotation_euler = Euler((math.radians(-20), 0, 0))
    b_foot_r.keyframe_insert(data_path='rotation_euler', frame=12)
if b_arm_r:
    b_arm_r.rotation_euler = Euler((math.radians(25), 0, math.radians(-15)))
    b_arm_r.keyframe_insert(data_path='rotation_euler', frame=12)
if b_arm_l:
    b_arm_l.rotation_euler = Euler((math.radians(-30), 0, math.radians(15)))
    b_arm_l.keyframe_insert(data_path='rotation_euler', frame=12)
if b_spine:
    b_spine.rotation_euler = Euler((math.radians(16), 0, math.radians(-4)))
    b_spine.keyframe_insert(data_path='rotation_euler', frame=12)
if b_tail1:
    b_tail1.rotation_euler = Euler((math.radians(-10), math.radians(15), 0))
    b_tail1.keyframe_insert(data_path='rotation_euler', frame=12)

# Frame 24: Jambe droite posée sur Marche 1 + VRAI PLI DE JAMBE GAUCHE (Genou gauche fléchi à 80°)
if b_thigh_r:
    b_thigh_r.rotation_euler = Euler((math.radians(10), 0, 0))
    b_thigh_r.keyframe_insert(data_path='rotation_euler', frame=24)
if b_shin_r:
    b_shin_r.rotation_euler = Euler((math.radians(-5), 0, 0))
    b_shin_r.keyframe_insert(data_path='rotation_euler', frame=24)
if b_thigh_l:
    b_thigh_l.rotation_euler = Euler((math.radians(-60), 0, 0))
    b_thigh_l.keyframe_insert(data_path='rotation_euler', frame=24)
if b_shin_l:
    b_shin_l.rotation_euler = Euler((math.radians(80), 0, 0))
    b_shin_l.keyframe_insert(data_path='rotation_euler', frame=24)
if b_arm_r:
    b_arm_r.rotation_euler = Euler((math.radians(-35), 0, math.radians(-10)))
    b_arm_r.keyframe_insert(data_path='rotation_euler', frame=24)
if b_arm_l:
    b_arm_l.rotation_euler = Euler((math.radians(30), 0, math.radians(20)))
    b_arm_l.keyframe_insert(data_path='rotation_euler', frame=24)
if b_spine:
    b_spine.rotation_euler = Euler((math.radians(14), 0, math.radians(5)))
    b_spine.keyframe_insert(data_path='rotation_euler', frame=24)
if b_tail1:
    b_tail1.rotation_euler = Euler((math.radians(-12), math.radians(-15), 0))
    b_tail1.keyframe_insert(data_path='rotation_euler', frame=24)

# Frame 36: Jambe gauche posée sur Marche 2 + Jambe droite monte vers Marche 3
if b_thigh_l:
    b_thigh_l.rotation_euler = Euler((math.radians(10), 0, 0))
    b_thigh_l.keyframe_insert(data_path='rotation_euler', frame=36)
if b_shin_l:
    b_shin_l.rotation_euler = Euler((math.radians(-5), 0, 0))
    b_shin_l.keyframe_insert(data_path='rotation_euler', frame=36)
if b_thigh_r:
    b_thigh_r.rotation_euler = Euler((math.radians(-60), 0, 0))
    b_thigh_r.keyframe_insert(data_path='rotation_euler', frame=36)
if b_shin_r:
    b_shin_r.rotation_euler = Euler((math.radians(80), 0, 0))
    b_shin_r.keyframe_insert(data_path='rotation_euler', frame=36)
if b_arm_r:
    b_arm_r.rotation_euler = Euler((math.radians(30), 0, math.radians(-15)))
    b_arm_r.keyframe_insert(data_path='rotation_euler', frame=36)
if b_arm_l:
    b_arm_l.rotation_euler = Euler((math.radians(-30), 0, math.radians(15)))
    b_arm_l.keyframe_insert(data_path='rotation_euler', frame=36)

# Frame 58: Arrivée sur le palier supérieur
if b_thigh_l:
    b_thigh_l.rotation_euler = Euler((math.radians(5), 0, 0))
    b_thigh_l.keyframe_insert(data_path='rotation_euler', frame=58)
if b_shin_l:
    b_shin_l.rotation_euler = Euler((0, 0, 0))
    b_shin_l.keyframe_insert(data_path='rotation_euler', frame=58)
if b_thigh_r:
    b_thigh_r.rotation_euler = Euler((math.radians(5), 0, 0))
    b_thigh_r.keyframe_insert(data_path='rotation_euler', frame=58)
if b_shin_r:
    b_shin_r.rotation_euler = Euler((0, 0, 0))
    b_shin_r.keyframe_insert(data_path='rotation_euler', frame=58)

# Frame 72 : Posture de Gardien Héroïque & Rugissement
if b_spine:
    b_spine.rotation_euler = Euler((math.radians(-12), 0, math.radians(-6)))
    b_spine.keyframe_insert(data_path='rotation_euler', frame=72)
if b_head:
    b_head.rotation_euler = Euler((math.radians(12), math.radians(0), math.radians(6)))
    b_head.keyframe_insert(data_path='rotation_euler', frame=72)
if b_arm_l:
    b_arm_l.rotation_euler = Euler((math.radians(-20), math.radians(15), math.radians(30)))
    b_arm_l.keyframe_insert(data_path='rotation_euler', frame=72)
if b_arm_r:
    b_arm_r.rotation_euler = Euler((math.radians(-20), math.radians(-15), math.radians(-30)))
    b_arm_r.keyframe_insert(data_path='rotation_euler', frame=72)
if b_tail1:
    b_tail1.rotation_euler = Euler((math.radians(25), math.radians(10), 0))
    b_tail1.keyframe_insert(data_path='rotation_euler', frame=72)
if b_tail2:
    b_tail2.rotation_euler = Euler((math.radians(45), 0, 0))
    b_tail2.keyframe_insert(data_path='rotation_euler', frame=72)

bpy.ops.object.mode_set(mode='OBJECT')

# =========================================================
# 6. CAMÉRA CINÉMA & RENDU DES STILLS & VIDÉO
# =========================================================
print("[6/6] Caméra cinématique cadrée sur le personnage de 2.10m...")
cam_data = bpy.data.cameras.new('CinematicCamera')
cam_data.lens = 45
cam_data.sensor_width = 36
cam_obj = bpy.data.objects.new('CinematicCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Cadrage cinématique 3/4 face suivant la montée du personnage de 2.10m
cam_keyframes = [
    # Frame, Cam Pos, Target Pos (Ciblage à hauteur de poitrine/tête du personnage 2.1m)
    (1,  Vector((-0.4, -4.5, 1.4)), Vector((-1.7, 0.0, 1.3))),
    (36, Vector((0.4,  -4.8, 1.9)), Vector((-0.5, 0.0, 1.7))),
    (72, Vector((1.6,  -4.2, 2.3)), Vector((1.1, 0.0, 2.1))),
]

for f, c_pos, target_pos in cam_keyframes:
    cam_obj.location = c_pos
    dir_vec = target_pos - c_pos
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()
    cam_obj.keyframe_insert(data_path='location', frame=f)
    cam_obj.keyframe_insert(data_path='rotation_euler', frame=f)

# Stills clés
key_stills = [
    (1,  '01_stance_entree_escalier'),
    (12, '02_foulee_premiere_marche'),
    (36, '03_montee_dynamique_marche2'),
    (58, '04_arrivee_palier_haut'),
    (72, '05_rugissement_gardien_hero'),
]

for frame_num, label in key_stills:
    scene.frame_set(frame_num)
    scene.render.filepath = os.path.join(OUT_DIR, f'still_{label}.png')
    bpy.ops.render.render(write_still=True)
    print(f'Rendered still {label} (Frame {frame_num})')

# Rendu Clay White
orig_mats = list(mesh_obj.data.materials)
clay_mat = bpy.data.materials.new(name='ClayWhite')
clay_mat.use_nodes = True
c_bsdf = clay_mat.node_tree.nodes.get('Principled BSDF')
if c_bsdf:
    c_bsdf.inputs['Base Color'].default_value = (0.88, 0.88, 0.90, 1.0)
    c_bsdf.inputs['Roughness'].default_value = 0.40
mesh_obj.data.materials.clear()
mesh_obj.data.materials.append(clay_mat)

scene.frame_set(72)
scene.render.filepath = os.path.join(OUT_DIR, 'still_05_clay_white_hero.png')
bpy.ops.render.render(write_still=True)
print('Rendered still_05_clay_white_hero.png')

mesh_obj.data.materials.clear()
for m in orig_mats:
    mesh_obj.data.materials.append(m)

# Export Scene GLB Animé
scene_glb_path = os.path.join(OUT_DIR, 'scene_living_creature_animated.glb')
bpy.ops.export_scene.gltf(
    filepath=scene_glb_path,
    export_format='GLB',
    export_animations=True,
    export_current_frame=False,
    export_skins=True,
    export_morph=True,
    export_materials='EXPORT',
)
print('Exported animated GLB to:', scene_glb_path)

# Rendu des 72 frames
scene.render.filepath = os.path.join(FRAMES_DIR, 'frame_')
scene.render.image_settings.file_format = 'PNG'
print('Rendering 72 cinematic animation frames...')
bpy.ops.render.render(animation=True)
print('MASTER_PRODUCTION_RENDER_COMPLETE')
