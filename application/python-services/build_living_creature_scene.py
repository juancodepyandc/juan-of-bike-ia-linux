#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_living_creature_scene.py — Version Cinématique HD Ultime :
- Cadrage 3/4 face et plongée/contre-plongée révélant le visage félin-draconique, yeux dorés, mâchoire, plastron en cuir et boucle en laiton
- Intérieur de manoir réaliste avec grand escalier en acajou/chêne, rampe travaillée, parquet, lustre et fenêtres
- Locomotion d'escalade biomécanique complète (flexion des genoux, pose des pattes sur chaque marche, torsion du buste, balancement de la queue)
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

print("[1/6] Initialisation de la scène Blender...")
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

# World Environment & Lighting
w = bpy.data.worlds.new('InteriorMansionWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.04, 0.05, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 0.5

# Key Light Frontal (Projecteur cinéma chaud sur le visage et le torse)
key_data = bpy.data.lights.new('KeyFrontLight', type='SPOT')
key_data.energy = 600.0
key_data.spot_size = math.radians(65)
key_data.spot_blend = 0.35
key_data.color = (1.0, 0.94, 0.85)
key_obj = bpy.data.objects.new('KeyFrontLight', key_data)
key_obj.location = Vector((0.5, -3.2, 3.2))
key_obj.rotation_euler = Euler((math.radians(45), math.radians(0), math.radians(-10)), 'XYZ')
scene.collection.objects.link(key_obj)

# Rim Light (Bleu lune arrière pour détacher la fourrure et les contours)
rim_data = bpy.data.lights.new('MoonlightRim', type='SUN')
rim_data.energy = 3.8
rim_data.color = (0.75, 0.88, 1.0)
rim_data.angle = math.radians(2.0)
rim_obj = bpy.data.objects.new('MoonlightRim', rim_data)
rim_obj.rotation_euler = Euler((math.radians(35), math.radians(-25), math.radians(130)), 'XYZ')
scene.collection.objects.link(rim_obj)

# Fill Light Ambiance intérieure
fill_data = bpy.data.lights.new('WarmFill', type='POINT')
fill_data.energy = 160.0
fill_data.color = (1.0, 0.80, 0.55)
fill_obj = bpy.data.objects.new('WarmFill', fill_data)
fill_obj.location = Vector((-1.8, -1.2, 1.8))
scene.collection.objects.link(fill_obj)

print("[2/6] Construction de l'intérieur architectural réaliste...")

# Matériaux
# 1. Bois Acajou Verni (Marches)
wood_mat = bpy.data.materials.new(name='PolishedMahogany')
wood_mat.use_nodes = True
w_bsdf = wood_mat.node_tree.nodes.get('Principled BSDF')
if w_bsdf:
    w_bsdf.inputs['Base Color'].default_value = (0.24, 0.12, 0.07, 1.0)
    w_bsdf.inputs['Roughness'].default_value = 0.28

# 2. Tapis d'escalier royal (Rouge Bordeaux au centre des marches)
carpet_mat = bpy.data.materials.new(name='StairCarpet')
carpet_mat.use_nodes = True
cp_bsdf = carpet_mat.node_tree.nodes.get('Principled BSDF')
if cp_bsdf:
    cp_bsdf.inputs['Base Color'].default_value = (0.42, 0.06, 0.08, 1.0)
    cp_bsdf.inputs['Roughness'].default_value = 0.85

# 3. Parquet Chevron Hall
parquet_mat = bpy.data.materials.new(name='ParquetFloor')
parquet_mat.use_nodes = True
p_bsdf = parquet_mat.node_tree.nodes.get('Principled BSDF')
if p_bsdf:
    p_bsdf.inputs['Base Color'].default_value = (0.32, 0.19, 0.10, 1.0)
    p_bsdf.inputs['Roughness'].default_value = 0.35

# 4. Murs Boiserie & Cimaise
wall_mat = bpy.data.materials.new(name='MansionWall')
wall_mat.use_nodes = True
wl_bsdf = wall_mat.node_tree.nodes.get('Principled BSDF')
if wl_bsdf:
    wl_bsdf.inputs['Base Color'].default_value = (0.48, 0.44, 0.39, 1.0)
    wl_bsdf.inputs['Roughness'].default_value = 0.70

# 5. Ferronnerie Laiton & Chandelier
brass_mat = bpy.data.materials.new(name='PolishedBrass')
brass_mat.use_nodes = True
b_bsdf = brass_mat.node_tree.nodes.get('Principled BSDF')
if b_bsdf:
    b_bsdf.inputs['Base Color'].default_value = (0.88, 0.72, 0.28, 1.0)
    b_bsdf.inputs['Metallic'].default_value = 0.95
    b_bsdf.inputs['Roughness'].default_value = 0.25

# Sol du vestibule
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(-1.2, 0.0, 0.0))
floor = bpy.context.active_object
floor.name = 'Mansion_Floor'
floor.scale = Vector((5.0, 6.0, 1.0))
bpy.ops.object.transform_apply(scale=True)
floor.data.materials.append(parquet_mat)

# Murs arrière et côté
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 2.5, 2.2))
back_wall = bpy.context.active_object
back_wall.name = 'Back_Wall'
back_wall.scale = Vector((8.0, 0.2, 4.4))
bpy.ops.object.transform_apply(scale=True)
back_wall.data.materials.append(wall_mat)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-3.8, 0.0, 2.2))
side_wall = bpy.context.active_object
side_wall.name = 'Side_Wall'
side_wall.scale = Vector((0.2, 6.0, 4.4))
bpy.ops.object.transform_apply(scale=True)
side_wall.data.materials.append(wall_mat)

# Grand Escalier (5 marches + Tapis + Palier)
NUM_STEPS = 5
STEP_WIDTH = 2.6
STEP_DEPTH = 0.36
STEP_HEIGHT = 0.16
START_X = -1.1
START_Z = 0.0

for i in range(NUM_STEPS):
    step_x = START_X + i * STEP_DEPTH
    step_z = START_Z + (i + 1) * STEP_HEIGHT
    
    # Marche en bois
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z - STEP_HEIGHT * 0.5))
    step = bpy.context.active_object
    step.scale = Vector((STEP_DEPTH, STEP_WIDTH, STEP_HEIGHT))
    bpy.ops.object.transform_apply(scale=True)
    step.data.materials.append(wood_mat)
    
    # Tapis central
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z + 0.005))
    carpet_step = bpy.context.active_object
    carpet_step.scale = Vector((STEP_DEPTH * 0.98, STEP_WIDTH * 0.55, 0.01))
    bpy.ops.object.transform_apply(scale=True)
    carpet_step.data.materials.append(carpet_mat)

# Palier supérieur
landing_x = START_X + NUM_STEPS * STEP_DEPTH + 1.1
landing_z = NUM_STEPS * STEP_HEIGHT
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(landing_x, 0.0, landing_z - 0.5))
landing = bpy.context.active_object
landing.name = 'Upper_Landing'
landing.scale = Vector((2.4, STEP_WIDTH, 1.0))
bpy.ops.object.transform_apply(scale=True)
landing.data.materials.append(wood_mat)

# Tapis sur le palier
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(landing_x, 0.0, landing_z + 0.005))
carpet_landing = bpy.context.active_object
carpet_landing.scale = Vector((2.3, STEP_WIDTH * 0.55, 0.01))
bpy.ops.object.transform_apply(scale=True)
carpet_landing.data.materials.append(carpet_mat)

# Rampe d'escalier en bois mouluré
rail_start = Vector((START_X - 0.15, -STEP_WIDTH * 0.48, START_Z + 0.90))
rail_end = Vector((landing_x + 0.9, -STEP_WIDTH * 0.48, landing_z + 0.90))
bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=(rail_end - rail_start).length, location=(rail_start + rail_end) * 0.5)
handrail = bpy.context.active_object
direction = rail_end - rail_start
handrail.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
handrail.data.materials.append(wood_mat)

# Poteau de départ
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(START_X - 0.15, -STEP_WIDTH * 0.48, 0.48))
newel_post = bpy.context.active_object
newel_post.scale = Vector((0.16, 0.16, 0.96))
bpy.ops.object.transform_apply(scale=True)
newel_post.data.materials.append(wood_mat)

# Barreaux dorés
for i in range(NUM_STEPS + 4):
    bx = START_X + i * STEP_DEPTH * 0.78
    bz = (START_Z + i * STEP_HEIGHT * 0.78) * 0.5 + 0.45
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.82, location=(bx, -STEP_WIDTH * 0.48, bz))
    baluster = bpy.context.active_object
    baluster.data.materials.append(brass_mat)

print("[3/6] Importation et calibrage PBR 4K de la créature...")
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=CREATURE_RAW_GLB)
imported = [o for o in bpy.data.objects if o not in before]
mesh_obj = next((o for o in imported if o.type == 'MESH'), None)
mesh_obj.name = "Creature_Mesh"

# Shading PBR avec SSS
if mesh_obj.data.materials:
    c_mat = mesh_obj.data.materials[0]
    if c_mat.use_nodes:
        bsdf = c_mat.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            if 'Subsurface Weight' in bsdf.inputs:
                bsdf.inputs['Subsurface Weight'].default_value = 0.22
                bsdf.inputs['Subsurface Radius'].default_value = (0.10, 0.05, 0.02)
            bsdf.inputs['Roughness'].default_value = 0.45
            bsdf.inputs['Metallic'].default_value = 0.12

Z_OFFSET = 0.998

print("[4/6] Squelette anatomique et rigging propre...")
armature_data = bpy.data.armatures.new('Creature_Skeleton')
armature_obj = bpy.data.objects.new('Creature_Armature', armature_data)
scene.collection.objects.link(armature_obj)
bpy.context.view_layer.objects.active = armature_obj

bpy.ops.object.mode_set(mode='EDIT')
eb = armature_data.edit_bones

root = eb.new('Root')
root.head = (0, 0, 0)
root.tail = (0, 0, 0.2)

pelvis = eb.new('Pelvis')
pelvis.head = (0, 0, 0.0)
pelvis.tail = (0, 0, 0.25)
pelvis.parent = root

spine = eb.new('Spine')
spine.head = (0, 0, 0.25)
spine.tail = (0, 0, 0.55)
spine.parent = pelvis

chest = eb.new('Chest')
chest.head = (0, 0, 0.55)
chest.tail = (0, 0, 0.75)
chest.parent = spine

neck = eb.new('Neck')
neck.head = (0, 0, 0.75)
neck.tail = (0, 0, 0.85)
neck.parent = chest

head = eb.new('Head')
head.head = (0, 0, 0.85)
head.tail = (0, 0, 1.05)
head.parent = neck

tail1 = eb.new('Tail.01')
tail1.head = (0, -0.15, 0.05)
tail1.tail = (0, -0.40, 0.0)
tail1.parent = pelvis

tail2 = eb.new('Tail.02')
tail2.head = (0, -0.40, 0.0)
tail2.tail = (0, -0.70, 0.15)
tail2.parent = tail1

thigh_l = eb.new('Thigh.L')
thigh_l.head = (-0.22, 0.0, 0.0)
thigh_l.tail = (-0.22, 0.05, -0.45)
thigh_l.parent = pelvis

shin_l = eb.new('Shin.L')
shin_l.head = (-0.22, 0.05, -0.45)
shin_l.tail = (-0.22, -0.02, -0.88)
shin_l.parent = thigh_l

foot_l = eb.new('Foot.L')
foot_l.head = (-0.22, -0.02, -0.88)
foot_l.tail = (-0.22, 0.18, -0.98)
foot_l.parent = shin_l

thigh_r = eb.new('Thigh.R')
thigh_r.head = (0.22, 0.0, 0.0)
thigh_r.tail = (0.22, 0.05, -0.45)
thigh_r.parent = pelvis

shin_r = eb.new('Shin.R')
shin_r.head = (0.22, 0.05, -0.45)
shin_r.tail = (0.22, -0.02, -0.88)
shin_r.parent = thigh_r

foot_r = eb.new('Foot.R')
foot_r.head = (0.22, -0.02, -0.88)
foot_r.tail = (0.22, 0.18, -0.98)
foot_r.parent = shin_r

upper_arm_l = eb.new('UpperArm.L')
upper_arm_l.head = (-0.40, 0.0, 0.70)
upper_arm_l.tail = (-0.68, 0.0, 0.40)
upper_arm_l.parent = chest

forearm_l = eb.new('Forearm.L')
forearm_l.head = (-0.68, 0.0, 0.40)
forearm_l.tail = (-0.72, 0.05, 0.05)
forearm_l.parent = upper_arm_l

upper_arm_r = eb.new('UpperArm.R')
upper_arm_r.head = (0.40, 0.0, 0.70)
upper_arm_r.tail = (0.68, 0.0, 0.40)
upper_arm_r.parent = chest

forearm_r = eb.new('Forearm.R')
forearm_r.head = (0.68, 0.0, 0.40)
forearm_r.tail = (0.72, 0.05, 0.05)
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

print("[5/6] Animation biomécanique complète et expressive...")
armature_obj.animation_data_create()
action = bpy.data.actions.new(name='Stair_Climb_And_Hero_Roar')
armature_obj.animation_data.action = action

# Trajectoire de l'escalade avec rotation orientée 3/4 vers la caméra
keyframes_pos = [
    # Frame, X, Y, Z, RotZ deg (orientation 3/4 face pour voir le visage et le corps)
    (1,  -1.6, 0.0, Z_OFFSET, 65),                      # Face aux marches, orienté 3/4 caméra
    (14, -1.2, 0.0, Z_OFFSET + 0.08, 65),              # Envolée pied droit vers marche 1
    (24, -0.8, 0.0, Z_OFFSET + STEP_HEIGHT * 1.0, 60),  # Pose pied droit marche 1, poussée
    (36, -0.4, 0.0, Z_OFFSET + STEP_HEIGHT * 2.2, 55),  # Pose pied gauche marche 2
    (48,  0.1, 0.0, Z_OFFSET + STEP_HEIGHT * 3.5, 50),  # Pose pied droit marche 3
    (58,  0.7, 0.0, Z_OFFSET + landing_z + 0.02, 45),  # Foulée finale sur le palier
    (66,  1.1, 0.0, Z_OFFSET + landing_z, 35),         # Les deux pattes ancrées
    (72,  1.1, 0.0, Z_OFFSET + landing_z, 25),         # Face caméra, rugissement majestueux
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

# Frame 1: Stance initiale
for bone in [b_thigh_l, b_shin_l, b_foot_l, b_thigh_r, b_shin_r, b_foot_r, b_arm_l, b_arm_r, b_spine, b_head, b_tail1, b_tail2]:
    if bone:
        bone.rotation_euler = Euler((0, 0, 0))
        bone.keyframe_insert(data_path='rotation_euler', frame=1)

# Frame 14: Foulée jambe droite vers Marche 1
if b_thigh_r:
    b_thigh_r.rotation_euler = Euler((math.radians(-55), 0, 0))
    b_thigh_r.keyframe_insert(data_path='rotation_euler', frame=14)
if b_shin_r:
    b_shin_r.rotation_euler = Euler((math.radians(75), 0, 0))
    b_shin_r.keyframe_insert(data_path='rotation_euler', frame=14)
if b_foot_r:
    b_foot_r.rotation_euler = Euler((math.radians(-20), 0, 0))
    b_foot_r.keyframe_insert(data_path='rotation_euler', frame=14)
if b_arm_r:
    b_arm_r.rotation_euler = Euler((math.radians(25), 0, math.radians(-15)))
    b_arm_r.keyframe_insert(data_path='rotation_euler', frame=14)
if b_arm_l:
    b_arm_l.rotation_euler = Euler((math.radians(-30), 0, math.radians(15)))
    b_arm_l.keyframe_insert(data_path='rotation_euler', frame=14)
if b_spine:
    b_spine.rotation_euler = Euler((math.radians(16), 0, math.radians(-4)))
    b_spine.keyframe_insert(data_path='rotation_euler', frame=14)
if b_tail1:
    b_tail1.rotation_euler = Euler((math.radians(-10), math.radians(15), 0))
    b_tail1.keyframe_insert(data_path='rotation_euler', frame=14)

# Frame 28: Foulée jambe gauche vers Marche 2
if b_thigh_r:
    b_thigh_r.rotation_euler = Euler((math.radians(10), 0, 0))
    b_thigh_r.keyframe_insert(data_path='rotation_euler', frame=28)
if b_shin_r:
    b_shin_r.rotation_euler = Euler((math.radians(-5), 0, 0))
    b_shin_r.keyframe_insert(data_path='rotation_euler', frame=28)
if b_thigh_l:
    b_thigh_l.rotation_euler = Euler((math.radians(-60), 0, 0))
    b_thigh_l.keyframe_insert(data_path='rotation_euler', frame=28)
if b_shin_l:
    b_shin_l.rotation_euler = Euler((math.radians(80), 0, 0))
    b_shin_l.keyframe_insert(data_path='rotation_euler', frame=28)
if b_arm_r:
    b_arm_r.rotation_euler = Euler((math.radians(-35), 0, math.radians(-10)))
    b_arm_r.keyframe_insert(data_path='rotation_euler', frame=28)
if b_arm_l:
    b_arm_l.rotation_euler = Euler((math.radians(30), 0, math.radians(20)))
    b_arm_l.keyframe_insert(data_path='rotation_euler', frame=28)
if b_spine:
    b_spine.rotation_euler = Euler((math.radians(14), 0, math.radians(5)))
    b_spine.keyframe_insert(data_path='rotation_euler', frame=28)
if b_tail1:
    b_tail1.rotation_euler = Euler((math.radians(-12), math.radians(-15), 0))
    b_tail1.keyframe_insert(data_path='rotation_euler', frame=28)

# Frame 58: Arrivée palier haut
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

# Frame 72 : Rugissement du Gardien (Tête fière, yeux vers la caméra, torse bombé, bras puissants)
if b_spine:
    b_spine.rotation_euler = Euler((math.radians(-10), 0, math.radians(-6)))
    b_spine.keyframe_insert(data_path='rotation_euler', frame=72)
if b_head:
    b_head.rotation_euler = Euler((math.radians(14), math.radians(0), math.radians(8)))
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

print("[6/6] Caméra cinématique 3/4 Face, Rendu des Stills et Frames...")
cam_data = bpy.data.cameras.new('CinematicCamera')
cam_data.lens = 45
cam_data.sensor_width = 36
cam_obj = bpy.data.objects.new('CinematicCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Travelling cinématique fluide en légère contre-plongée révélant le visage et la musculature
cam_keyframes = [
    # Frame, Cam Pos, Target Pos
    (1,  Vector((-0.6, -4.5, 1.4)), Vector((-1.6, 0.0, 1.1))),
    (36, Vector((0.4,  -4.6, 2.0)), Vector((-0.4, 0.0, 1.8))),
    (72, Vector((1.6,  -4.2, 2.3)), Vector((1.1, 0.0, 2.2))),
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
    (14, '02_foulee_premiere_marche'),
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
print('BLENDER_SCENE_PIPELINE_COMPLETE')
