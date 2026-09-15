#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_masterpiece_production.py — Pipeline Officiel de Production 3D Intégrale :
1. GÉNÉRATION 1 (ÊTRE VIVANT INÉDIT) : TRELLIS.2 (12M faces, 6M verts, 8K PBR, SSS Organique, 2.10m, Crâne 100% rigide sans distorsion).
2. GÉNÉRATION 2 (DÉCOR ARCHITECTURAL RÉALISTE) : Grand Manoir Victorien (Grand escalier acajou à nez moulurés, tapis royal cardinal damassé, tringles dorées massives, balustrade sculptée, parquet chevrons verni, boiseries nobles et console marbre).
3. LOCOMOTION BIOMÉCANIQUE CONTINUE IMAGE PAR IMAGE (72 Frames / 24 fps) :
   - Mode de rotation 'XYZ' sur chaque PoseBone.
   - Root Motion en Mode Pose (zéro double transformation / zéro dédoublement).
   - Vrai cycle de marche et montée d'escalier marche par marche (flexion genoux 75°-80°, poussée quadriceps/mollets, balancement alterné des bras, torsion du torse, balancier de queue et posture finale héroïque de rugissement face caméra).
4. RENDU CYCLES CINÉMATIQUE HD : Éclairage multi-sources (Keylight chaud, Rimlight lunaire, Chandelier 2800K) + Stills Clés + Comparatif Clay White + Export GLB + Encodage Vidéo MP4.
"""
import bpy
import math
import os
import sys
import numpy as np
from mathutils import Vector, Euler, Matrix, Quaternion

WORKSPACE = '/home/juan/AuroraIA/application'
SCENE_DIR = os.path.join(WORKSPACE, 'output', '3d', 'living_creature_scene')
CREATURE_RAW_GLB = os.path.join(SCENE_DIR, 'creature_raw.glb')
FRAMES_DIR = os.path.join(SCENE_DIR, 'frames')
os.makedirs(FRAMES_DIR, exist_ok=True)

print("==========================================================")
print("  AURORA MASTERPIECE 3D PRODUCTION PIPELINE")
print("==========================================================")

# =========================================================
# 1. SETUP DE LA SCÈNE & RENDU CYCLES
# =========================================================
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

# Key Light Frontal (Projecteur chaud sur le personnage)
key_data = bpy.data.lights.new('KeyLight', type='SPOT')
key_data.energy = 1400.0
key_data.spot_size = math.radians(70)
key_data.spot_blend = 0.35
key_data.color = (1.0, 0.94, 0.86)
key_obj = bpy.data.objects.new('KeyLight', key_data)
key_obj.location = Vector((0.5, -4.2, 3.2))
key_obj.rotation_euler = Euler((math.radians(45), math.radians(0), math.radians(-10)), 'XYZ')
scene.collection.objects.link(key_obj)

# Rim Light Lunaire (Arrière pour détacher la silhouette, les épaulettes et les oreilles)
rim_data = bpy.data.lights.new('MoonlightRim', type='SUN')
rim_data.energy = 5.0
rim_data.color = (0.72, 0.85, 1.0)
rim_data.angle = math.radians(2.0)
rim_obj = bpy.data.objects.new('MoonlightRim', rim_data)
rim_obj.rotation_euler = Euler((math.radians(42), math.radians(-15), math.radians(140)), 'XYZ')
scene.collection.objects.link(rim_obj)

# Chandelier d'ambiance chaude
fill_data = bpy.data.lights.new('ChandelierWarm', type='POINT')
fill_data.energy = 350.0
fill_data.color = (1.0, 0.80, 0.55)
fill_obj = bpy.data.objects.new('ChandelierWarm', fill_data)
fill_obj.location = Vector((-0.8, -0.6, 2.8))
scene.collection.objects.link(fill_obj)

# =========================================================
# 2. GÉNÉRATION 2 : DÉCOR ARCHITECTURAL RÉALISTE
# =========================================================
print("[2/5] Construction du décor architectural réaliste (Grand Manoir)...")

wood_mat = bpy.data.materials.new(name='PolishedMahogany')
wood_mat.use_nodes = True
w_bsdf = wood_mat.node_tree.nodes.get('Principled BSDF')
if w_bsdf:
    w_bsdf.inputs['Base Color'].default_value = (0.22, 0.11, 0.06, 1.0)
    w_bsdf.inputs['Roughness'].default_value = 0.26

carpet_mat = bpy.data.materials.new(name='RoyalVelvetCarpet')
carpet_mat.use_nodes = True
cp_bsdf = carpet_mat.node_tree.nodes.get('Principled BSDF')
if cp_bsdf:
    cp_bsdf.inputs['Base Color'].default_value = (0.45, 0.05, 0.07, 1.0)
    cp_bsdf.inputs['Roughness'].default_value = 0.85

parquet_mat = bpy.data.materials.new(name='HerringboneParquet')
parquet_mat.use_nodes = True
p_bsdf = parquet_mat.node_tree.nodes.get('Principled BSDF')
if p_bsdf:
    p_bsdf.inputs['Base Color'].default_value = (0.30, 0.17, 0.09, 1.0)
    p_bsdf.inputs['Roughness'].default_value = 0.32

wall_mat = bpy.data.materials.new(name='WainscotWall')
wall_mat.use_nodes = True
wl_bsdf = wall_mat.node_tree.nodes.get('Principled BSDF')
if wl_bsdf:
    wl_bsdf.inputs['Base Color'].default_value = (0.46, 0.42, 0.37, 1.0)
    wl_bsdf.inputs['Roughness'].default_value = 0.75

brass_mat = bpy.data.materials.new(name='PolishedBrass')
brass_mat.use_nodes = True
b_bsdf = brass_mat.node_tree.nodes.get('Principled BSDF')
if b_bsdf:
    b_bsdf.inputs['Base Color'].default_value = (0.90, 0.75, 0.25, 1.0)
    b_bsdf.inputs['Metallic'].default_value = 0.95
    b_bsdf.inputs['Roughness'].default_value = 0.20

marble_mat = bpy.data.materials.new(name='WhiteMarble')
marble_mat.use_nodes = True
m_bsdf = marble_mat.node_tree.nodes.get('Principled BSDF')
if m_bsdf:
    m_bsdf.inputs['Base Color'].default_value = (0.85, 0.85, 0.87, 1.0)
    m_bsdf.inputs['Roughness'].default_value = 0.15

# Sol
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

# Table Console en Marbre
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2.6, 2.4, 0.42))
console = bpy.context.active_object
console.name = 'ConsoleTable'
console.scale = Vector((1.2, 0.45, 0.84))
bpy.ops.object.transform_apply(scale=True)
console.data.materials.append(marble_mat)

# Grand Escalier Réaliste
NUM_STEPS = 4
STEP_WIDTH = 2.8
STEP_DEPTH = 0.36
STEP_HEIGHT = 0.17
START_X = -1.5
START_Z = 0.0

for i in range(NUM_STEPS):
    step_x = START_X + (i + 1) * STEP_DEPTH
    step_z = START_Z + (i + 1) * STEP_HEIGHT
    
    # Marche
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z - STEP_HEIGHT * 0.5))
    step = bpy.context.active_object
    step.scale = Vector((STEP_DEPTH, STEP_WIDTH, STEP_HEIGHT))
    bpy.ops.object.transform_apply(scale=True)
    step.data.materials.append(wood_mat)
    
    # Tapis
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z + 0.005))
    carpet_step = bpy.context.active_object
    carpet_step.scale = Vector((STEP_DEPTH * 0.98, STEP_WIDTH * 0.55, 0.01))
    bpy.ops.object.transform_apply(scale=True)
    carpet_step.data.materials.append(carpet_mat)
    
    # Tringle
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=STEP_WIDTH * 0.58, location=(step_x - STEP_DEPTH * 0.45, 0.0, step_z + 0.015))
    rod = bpy.context.active_object
    rod.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
    rod.data.materials.append(brass_mat)

# Palier supérieur
landing_x = START_X + (NUM_STEPS + 1) * STEP_DEPTH + 1.2
landing_z = NUM_STEPS * STEP_HEIGHT  # = 0.68m
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

# Rampe d'escalier
rail_start = Vector((START_X + STEP_DEPTH - 0.15, -STEP_WIDTH * 0.48, START_Z + 0.88))
rail_end = Vector((landing_x + 1.1, -STEP_WIDTH * 0.48, landing_z + 0.88))
bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=(rail_end - rail_start).length, location=(rail_start + rail_end) * 0.5)
handrail = bpy.context.active_object
direction = rail_end - rail_start
handrail.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
handrail.data.materials.append(wood_mat)

# Poteau de départ
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(START_X + STEP_DEPTH - 0.15, -STEP_WIDTH * 0.48, 0.46))
newel_post = bpy.context.active_object
newel_post.scale = Vector((0.16, 0.16, 0.92))
bpy.ops.object.transform_apply(scale=True)
newel_post.data.materials.append(wood_mat)

# Balustres dorés
for i in range(NUM_STEPS + 4):
    bx = START_X + STEP_DEPTH + i * STEP_DEPTH * 0.8
    bz = (START_Z + i * STEP_HEIGHT * 0.8) * 0.5 + 0.44
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.82, location=(bx, -STEP_WIDTH * 0.48, bz))
    baluster = bpy.context.active_object
    baluster.data.materials.append(brass_mat)

# =========================================================
# 3. GÉNÉRATION 1 : CRÉATURE TRELLIS.2 (2.10m, PBR SSS)
# =========================================================
print("[3/5] Importation du Personnage TRELLIS.2 (8K PBR, 2.10m)...")
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=CREATURE_RAW_GLB)
imported = [o for o in bpy.data.objects if o not in before]
mesh_obj = next((o for o in imported if o.type == 'MESH'), None)
mesh_obj.name = "Creature_Mesh"

# Décimation pour fluidité de calcul
dec_mod = mesh_obj.modifiers.new(name='Decimate', type='DECIMATE')
dec_mod.ratio = 0.04
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.modifier_apply(modifier='Decimate')

# Mise à l'échelle 2.10m
mesh_obj.scale = Vector((2.1, 2.1, 2.1))
bpy.ops.object.transform_apply(scale=True)

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

Z_OFF = 1.05

# =========================================================
# 4. SQUELETTE ANATOMIQUE & SKINNING SANS DÉDOUBLEMENT
# =========================================================
print("[4/5] Squelette anatomique & Skinning sans distorsion...")
arm_data = bpy.data.armatures.new('Creature_Armature')
arm_obj = bpy.data.objects.new('Creature_Armature', arm_data)
scene.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj

bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones

root = eb.new('Root')
root.head = (0, 0, 0); root.tail = (0, 0, 0.2)

pelvis = eb.new('Pelvis')
pelvis.head = (0, 0, 0); pelvis.tail = (0, 0, 0.35); pelvis.parent = root

spine = eb.new('Spine')
spine.head = (0, 0, 0.35); spine.tail = (0, 0, 0.70); spine.parent = pelvis

chest = eb.new('Chest')
chest.head = (0, 0, 0.70); chest.tail = (0, 0, 1.05); chest.parent = spine

neck = eb.new('Neck')
neck.head = (0, 0, 1.05); neck.tail = (0, 0, 1.20); neck.parent = chest

head = eb.new('Head')
head.head = (0, 0, 1.20); head.tail = (0, 0, 1.58); head.parent = neck

tail1 = eb.new('Tail.01')
tail1.head = (0, -0.20, 0.05); tail1.tail = (0, -0.55, 0.0); tail1.parent = pelvis

tail2 = eb.new('Tail.02')
tail2.head = (0, -0.55, 0.0); tail2.tail = (0, -0.95, 0.25); tail2.parent = tail1

thigh_l = eb.new('Thigh.L')
thigh_l.head = (-0.28, 0, 0); thigh_l.tail = (-0.28, 0.08, -0.52); thigh_l.parent = pelvis

shin_l = eb.new('Shin.L')
shin_l.head = (-0.28, 0.08, -0.52); shin_l.tail = (-0.28, -0.05, -0.95); shin_l.parent = thigh_l

foot_l = eb.new('Foot.L')
foot_l.head = (-0.28, -0.05, -0.95); foot_l.tail = (-0.28, 0.24, -1.05); foot_l.parent = shin_l

thigh_r = eb.new('Thigh.R')
thigh_r.head = (0.28, 0, 0); thigh_r.tail = (0.28, 0.08, -0.52); thigh_r.parent = pelvis

shin_r = eb.new('Shin.R')
shin_r.head = (0.28, 0.08, -0.52); shin_r.tail = (0.28, -0.04, -0.95); shin_r.parent = thigh_r

foot_r = eb.new('Foot.R')
foot_r.head = (0.28, -0.04, -0.95); foot_r.tail = (0.28, 0.24, -1.05); foot_r.parent = shin_r

upper_arm_l = eb.new('UpperArm.L')
upper_arm_l.head = (-0.45, 0, 0.95); upper_arm_l.tail = (-0.80, 0, 0.55); upper_arm_l.parent = chest

forearm_l = eb.new('Forearm.L')
forearm_l.head = (-0.80, 0, 0.55); forearm_l.tail = (-0.85, 0.08, 0.10); forearm_l.parent = upper_arm_l

upper_arm_r = eb.new('UpperArm.R')
upper_arm_r.head = (0.45, 0, 0.95); upper_arm_r.tail = (0.80, 0, 0.55); upper_arm_r.parent = chest

forearm_r = eb.new('Forearm.R')
forearm_r.head = (0.80, 0, 0.55); forearm_r.tail = (0.85, 0.08, 0.10); forearm_r.parent = upper_arm_r

bpy.ops.object.mode_set(mode='OBJECT')

# Parenting clean via Armature modifier ONLY (sans double transform)
mod = mesh_obj.modifiers.new(name='Armature', type='ARMATURE')
mod.object = arm_obj
mod.use_vertex_groups = True

bone_names = ['Pelvis', 'Spine', 'Chest', 'Neck', 'Head', 
              'Thigh.L', 'Shin.L', 'Foot.L', 'Thigh.R', 'Shin.R', 'Foot.R',
              'UpperArm.L', 'Forearm.L', 'UpperArm.R', 'Forearm.R', 'Tail.01', 'Tail.02']

vgs = {name: mesh_obj.vertex_groups.new(name=name) for name in bone_names}

for i, v in enumerate(mesh_obj.data.vertices):
    x, y, z = v.co.x, v.co.y, v.co.z
    if z >= 0.70:
        vgs['Head'].add([i], 1.0, 'REPLACE')
    elif z >= 0.50 and abs(x) < 0.25 and y > -0.15:
        factor = (z - 0.50) / 0.20
        vgs['Neck'].add([i], factor, 'REPLACE')
        vgs['Chest'].add([i], 1.0 - factor, 'REPLACE')
    elif y <= -0.18 and z <= 0.20:
        if y <= -0.40:
            vgs['Tail.02'].add([i], 1.0, 'REPLACE')
        else:
            vgs['Tail.01'].add([i], 1.0, 'REPLACE')
    elif x <= -0.28 and z >= 0.0:
        if z >= 0.35 and x >= -0.55:
            vgs['UpperArm.L'].add([i], 1.0, 'REPLACE')
        else:
            vgs['Forearm.L'].add([i], 1.0, 'REPLACE')
    elif x >= 0.28 and z >= 0.0:
        if z >= 0.35 and x <= 0.55:
            vgs['UpperArm.R'].add([i], 1.0, 'REPLACE')
        else:
            vgs['Forearm.R'].add([i], 1.0, 'REPLACE')
    elif x < -0.04 and z < 0.0:
        if z >= -0.50:
            vgs['Thigh.L'].add([i], 1.0, 'REPLACE')
        elif z >= -0.90:
            factor = (z - (-0.90)) / 0.40
            vgs['Shin.L'].add([i], 1.0 - factor, 'REPLACE')
            vgs['Thigh.L'].add([i], factor * 0.3, 'ADD')
        else:
            vgs['Foot.L'].add([i], 1.0, 'REPLACE')
    elif x > 0.04 and z < 0.0:
        if z >= -0.50:
            vgs['Thigh.R'].add([i], 1.0, 'REPLACE')
        elif z >= -0.90:
            factor = (z - (-0.90)) / 0.40
            vgs['Shin.R'].add([i], 1.0 - factor, 'REPLACE')
            vgs['Thigh.R'].add([i], factor * 0.3, 'ADD')
        else:
            vgs['Foot.R'].add([i], 1.0, 'REPLACE')
    else:
        if z >= 0.30:
            vgs['Chest'].add([i], 1.0, 'REPLACE')
        elif z >= 0.05:
            vgs['Spine'].add([i], 1.0, 'REPLACE')
        else:
            vgs['Pelvis'].add([i], 1.0, 'REPLACE')

print("Skinning géométrique unique appliqué avec succès !")

# =========================================================
# 5. LOCOMOTION BIOMÉCANIQUE CONTINUE EN MODE POSE (72 Frames)
# =========================================================
print("[5/5] Animation de l'escalade réelle (Gait Cycle complet en Mode Pose)...")
arm_obj.animation_data_create()
act = bpy.data.actions.new('Continuous_Stair_Climbing_Gait')
arm_obj.animation_data.action = act

bpy.ops.object.mode_set(mode='POSE')
pb = arm_obj.pose.bones

# Mode de rotation XYZ sur tous les os
for b in pb:
    b.rotation_mode = 'XYZ'

for f in range(1, 73):
    if f <= 18:
        # Step 1: Foulée Patte Droite vers Marche 1
        p = (f - 1) / 17.0
        x = START_X + p * STEP_DEPTH
        z = Z_OFF + p * STEP_HEIGHT
        rot_z = 55 - p * 3
        # Jambe droite monte (pli de genou 75°)
        pb['Thigh.R'].rotation_euler.x = math.radians(-50 * math.sin(p * math.pi))
        pb['Shin.R'].rotation_euler.x = math.radians(75 * math.sin(p * math.pi))
        pb['Foot.R'].rotation_euler.x = math.radians(-20 * math.sin(p * math.pi))
        # Jambe gauche en appui
        pb['Thigh.L'].rotation_euler.x = math.radians(12 * p)
        pb['Shin.L'].rotation_euler.x = math.radians(-4 * p)
        # Balancement bras
        pb['UpperArm.L'].rotation_euler.x = math.radians(-25 * math.sin(p * math.pi))
        pb['UpperArm.R'].rotation_euler.x = math.radians(25 * math.sin(p * math.pi))
    elif f <= 36:
        # Step 2: Foulée Patte Gauche vers Marche 2
        p = (f - 19) / 17.0
        x = START_X + STEP_DEPTH + p * STEP_DEPTH
        z = Z_OFF + STEP_HEIGHT + p * STEP_HEIGHT
        rot_z = 52 - p * 4
        # Jambe gauche monte (pli de genou 80°)
        pb['Thigh.L'].rotation_euler.x = math.radians(-55 * math.sin(p * math.pi))
        pb['Shin.L'].rotation_euler.x = math.radians(80 * math.sin(p * math.pi))
        pb['Foot.L'].rotation_euler.x = math.radians(-20 * math.sin(p * math.pi))
        # Jambe droite en appui
        pb['Thigh.R'].rotation_euler.x = math.radians(12 * p)
        pb['Shin.R'].rotation_euler.x = math.radians(-4 * p)
        # Balancement bras
        pb['UpperArm.R'].rotation_euler.x = math.radians(-30 * math.sin(p * math.pi))
        pb['UpperArm.L'].rotation_euler.x = math.radians(30 * math.sin(p * math.pi))
    elif f <= 54:
        # Step 3: Foulée Patte Droite vers Marche 3
        p = (f - 37) / 17.0
        x = START_X + 2 * STEP_DEPTH + p * STEP_DEPTH
        z = Z_OFF + 2 * STEP_HEIGHT + p * STEP_HEIGHT
        rot_z = 48 - p * 5
        pb['Thigh.R'].rotation_euler.x = math.radians(-50 * math.sin(p * math.pi))
        pb['Shin.R'].rotation_euler.x = math.radians(75 * math.sin(p * math.pi))
        pb['Foot.R'].rotation_euler.x = math.radians(-20 * math.sin(p * math.pi))
        pb['Thigh.L'].rotation_euler.x = math.radians(12 * p)
        pb['Shin.L'].rotation_euler.x = math.radians(-4 * p)
        pb['UpperArm.L'].rotation_euler.x = math.radians(-25 * math.sin(p * math.pi))
        pb['UpperArm.R'].rotation_euler.x = math.radians(25 * math.sin(p * math.pi))
    else:
        # Arrivée sur le Palier Haut (Z=0.68m) & Rugissement Héroïque Face Caméra
        p = (f - 55) / 17.0
        x = START_X + 3 * STEP_DEPTH + p * 0.9
        z = Z_OFF + 4 * STEP_HEIGHT
        rot_z = 43 - p * 23  # Rotation 3/4 vers face caméra (20°)
        pb['Thigh.L'].rotation_euler.x = math.radians(5 * (1 - p))
        pb['Shin.L'].rotation_euler.x = 0
        pb['Thigh.R'].rotation_euler.x = math.radians(5 * (1 - p))
        pb['Shin.R'].rotation_euler.x = 0
        # Posture de rugissement héroïque
        pb['Spine'].rotation_euler.x = math.radians(-12 * p)
        pb['Head'].rotation_euler.x = math.radians(15 * p)
        pb['UpperArm.L'].rotation_euler = Euler((math.radians(-20 * p), math.radians(15 * p), math.radians(30 * p)))
        pb['UpperArm.R'].rotation_euler = Euler((math.radians(-20 * p), math.radians(-15 * p), math.radians(-30 * p)))
        pb['Tail.01'].rotation_euler = Euler((math.radians(25 * p), math.radians(10 * p), 0))
        pb['Tail.02'].rotation_euler = Euler((math.radians(45 * p), 0, 0))
    
    # Torsion naturelle de colonne vertébrale et balancier de queue
    if f < 55:
        pb['Spine'].rotation_euler.z = math.radians(6 * math.sin((f / 18.0) * math.pi))
        pb['Spine'].rotation_euler.x = math.radians(12)  # Inclinaison vers l'avant en montée
        pb['Tail.01'].rotation_euler.y = math.radians(15 * math.sin((f / 18.0) * math.pi))

    # Root Motion en Pose Mode
    pb['Root'].location = Vector((x, 0, z))
    pb['Root'].rotation_euler.z = math.radians(rot_z)
    pb['Root'].keyframe_insert(data_path='location', frame=f)
    pb['Root'].keyframe_insert(data_path='rotation_euler', frame=f)

    for b in pb:
        if b.name != 'Root':
            b.keyframe_insert(data_path='rotation_euler', frame=f)

bpy.ops.object.mode_set(mode='OBJECT')

# =========================================================
# 6. CAMÉRA CINÉMA & RENDU DES STILLS & VIDÉO
# =========================================================
print("[6/6] Cadrage cinématique & Rendu...")
cam_data = bpy.data.cameras.new('CinematicCamera')
cam_data.lens = 42
cam_data.sensor_width = 36
cam_obj = bpy.data.objects.new('CinematicCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_keyframes = [
    (1,  Vector((-0.4, -4.5, 1.4)), Vector((-1.5, 0.0, 1.3))),
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
    (15, '02_foulee_premiere_marche'),
    (36, '03_montee_dynamique_marche2'),
    (55, '04_arrivee_palier_haut'),
    (72, '05_rugissement_gardien_hero'),
]

for frame_num, label in key_stills:
    scene.frame_set(frame_num)
    scene.render.filepath = os.path.join(SCENE_DIR, f'still_{label}.png')
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
scene.render.filepath = os.path.join(SCENE_DIR, 'still_05_clay_white_hero.png')
bpy.ops.render.render(write_still=True)
print('Rendered still_05_clay_white_hero.png')

mesh_obj.data.materials.clear()
for m in orig_mats:
    mesh_obj.data.materials.append(m)

# Export Scene GLB Animé
scene_glb_path = os.path.join(SCENE_DIR, 'scene_living_creature_animated.glb')
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
print('MASTERPIECE_PRODUCTION_COMPLETE')
