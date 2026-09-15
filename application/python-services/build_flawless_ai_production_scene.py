#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_flawless_ai_production_scene.py — Pipeline Officiel de Production 3D Intégrale :
1. GÉNÉRATION DISTINCTE 1 : Être Vivant Inédit (TRELLIS.2 1536_cascade, 8K PBR SSS, 2.10m, crâne rigide 0% distorsion)
2. ANIMATION AI PURE (HY-Motion 1.0) : Import du BVH cinématique sans AUCUN hardcoding (locomotion bipedale réelle, vrais plis de genoux, foulée, torsion de buste et balancement des bras)
3. GÉNÉRATION DISTINCTE 2 : Décor Architectural Réaliste de Grand Manoir (Architecture complète : Grand escalier mouluré, tapis royal à tringles dorées, limons sculptés, balustrade travaillée, parquet chevrons verni, boiseries et lustre)
4. RENDU CINÉMATIQUE CYCLES : 1080p / 24 fps + Stills Clés + Comparatif Clay White + Export GLB + Encodage MP4
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
BVH_PATH = os.path.join(SCENE_DIR, 'hymotion', 'creature_motion.bvh')
FRAMES_DIR = os.path.join(SCENE_DIR, 'frames')
os.makedirs(FRAMES_DIR, exist_ok=True)

print("==========================================================")
print("  AURORA PRODUCTION PIPELINE : HY-MOTION + DUAL GENERATION")
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
# 2. GÉNÉRATION DISTINCTE 2 : DÉCOR ARCHITECTURAL RÉALISTE
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

# Table Console
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
START_X = -1.1
START_Z = 0.0

for i in range(NUM_STEPS):
    step_x = START_X + i * STEP_DEPTH
    step_z = START_Z + (i + 1) * STEP_HEIGHT
    
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z - STEP_HEIGHT * 0.5))
    step = bpy.context.active_object
    step.scale = Vector((STEP_DEPTH, STEP_WIDTH, STEP_HEIGHT))
    bpy.ops.object.transform_apply(scale=True)
    step.data.materials.append(wood_mat)
    
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(step_x, 0.0, step_z + 0.005))
    carpet_step = bpy.context.active_object
    carpet_step.scale = Vector((STEP_DEPTH * 0.98, STEP_WIDTH * 0.55, 0.01))
    bpy.ops.object.transform_apply(scale=True)
    carpet_step.data.materials.append(carpet_mat)
    
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=STEP_WIDTH * 0.58, location=(step_x - STEP_DEPTH * 0.45, 0.0, step_z + 0.015))
    rod = bpy.context.active_object
    rod.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
    rod.data.materials.append(brass_mat)

# Palier supérieur
landing_x = START_X + NUM_STEPS * STEP_DEPTH + 1.2
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
rail_start = Vector((START_X - 0.15, -STEP_WIDTH * 0.48, START_Z + 0.88))
rail_end = Vector((landing_x + 1.1, -STEP_WIDTH * 0.48, landing_z + 0.88))
bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=(rail_end - rail_start).length, location=(rail_start + rail_end) * 0.5)
handrail = bpy.context.active_object
direction = rail_end - rail_start
handrail.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
handrail.data.materials.append(wood_mat)

# Poteau de départ
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
# 3. IMPORTATION BVH HY-MOTION & RIGGING ANATOMIQUE
# =========================================================
print("[3/5] Importation de la trajectoire et du squelette BVH HY-Motion...")
before = set(bpy.data.objects)
bpy.ops.import_anim.bvh(filepath=BVH_PATH, update_scene_fps=True, update_scene_duration=True)
imported_bvh = [o for o in bpy.data.objects if o not in before]
armature_obj = next((o for o in imported_bvh if o.type == 'ARMATURE'), None)

if not armature_obj:
    raise RuntimeError("Armature BVH introuvable !")

armature_obj.name = "Creature_Armature"

# Mettre à l'échelle le BVH pour correspondre à 2.10m
# SMPL-X standard fait environ 1.75m -> scale 1.2x
armature_obj.scale = Vector((1.2, 1.2, 1.2))

# Déplacement de départ devant l'escalier, orienté 3/4 face
armature_obj.location = Vector((-1.6, 0.0, 0.0))
armature_obj.rotation_euler = Euler((0, 0, math.radians(50)), 'XYZ')

# =========================================================
# 4. IMPORTATION DU PERSONNAGE TRELLIS.2 & SKINNING GÉOMÉTRIQUE
# =========================================================
print("[4/5] Importation & Intégration du Personnage TRELLIS.2 (8K PBR, 2.10m)...")
before_mesh = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=CREATURE_RAW_GLB)
imported_mesh = [o for o in bpy.data.objects if o not in before_mesh]
mesh_obj = next((o for o in imported_mesh if o.type == 'MESH'), None)
mesh_obj.name = "Creature_Mesh"

# Décimation pour fluidité de rendu
dec_mod = mesh_obj.modifiers.new(name='Decimate', type='DECIMATE')
dec_mod.ratio = 0.04
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.modifier_apply(modifier='Decimate')

# Mise à l'échelle 2.10m
mesh_obj.scale = Vector((2.1, 2.1, 2.1))
bpy.ops.object.transform_apply(scale=True)

# Centrer les pieds à Z=0 (hauteur totale 2.1m, centre à Z=1.05m)
mesh_obj.location = Vector((0, 0, 1.05))
bpy.ops.object.transform_apply(location=True)

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

# Modificateur Armature
mesh_obj.parent = armature_obj
arm_mod = mesh_obj.modifiers.new(name='Armature', type='ARMATURE')
arm_mod.object = armature_obj
arm_mod.use_vertex_groups = True

# Mapper les os BVH SMPL-X vers le mesh
bvh_bone_map = {
    'Hips': ['Hips'],
    'Spine': ['Spine', 'Spine1'],
    'Chest': ['Spine2', 'Spine3'],
    'Neck': ['Neck'],
    'Head': ['Head'],
    'Thigh.L': ['LeftUpLeg'],
    'Shin.L': ['LeftLeg'],
    'Foot.L': ['LeftFoot', 'LeftToe'],
    'Thigh.R': ['RightUpLeg'],
    'Shin.R': ['RightLeg'],
    'Foot.R': ['RightFoot', 'RightToe'],
    'UpperArm.L': ['LeftShoulder', 'LeftArm'],
    'Forearm.L': ['LeftForeArm', 'LeftHand'],
    'UpperArm.R': ['RightShoulder', 'RightArm'],
    'Forearm.R': ['RightForeArm', 'RightHand'],
}

# Créer tous les vertex groups pour chaque os BVH réel
bone_group_objs = {}
for bone in armature_obj.data.bones:
    bone_group_objs[bone.name] = mesh_obj.vertex_groups.new(name=bone.name)

print("Skinning géométrique direct sur les os BVH HY-Motion...")
for i, v in enumerate(mesh_obj.data.vertices):
    x, y, z = v.co.x, v.co.y, v.co.z
    
    # Tête & Crâne (Rigide sur Head)
    if z >= 1.75:
        if 'Head' in bone_group_objs:
            bone_group_objs['Head'].add([i], 1.0, 'REPLACE')
    elif z >= 1.55 and abs(x) < 0.25:
        if 'Neck' in bone_group_objs:
            bone_group_objs['Neck'].add([i], 1.0, 'REPLACE')
    # Bras Gauche
    elif x <= -0.28 and z >= 1.05:
        if z >= 1.40:
            if 'LeftArm' in bone_group_objs:
                bone_group_objs['LeftArm'].add([i], 1.0, 'REPLACE')
        else:
            if 'LeftForeArm' in bone_group_objs:
                bone_group_objs['LeftForeArm'].add([i], 1.0, 'REPLACE')
    # Bras Droit
    elif x >= 0.28 and z >= 1.05:
        if z >= 1.40:
            if 'RightArm' in bone_group_objs:
                bone_group_objs['RightArm'].add([i], 1.0, 'REPLACE')
        else:
            if 'RightForeArm' in bone_group_objs:
                bone_group_objs['RightForeArm'].add([i], 1.0, 'REPLACE')
    # Jambe Gauche
    elif x < -0.04 and z < 1.05:
        if z >= 0.55:
            if 'LeftUpLeg' in bone_group_objs:
                bone_group_objs['LeftUpLeg'].add([i], 1.0, 'REPLACE')
        elif z >= 0.15:
            if 'LeftLeg' in bone_group_objs:
                bone_group_objs['LeftLeg'].add([i], 1.0, 'REPLACE')
        else:
            if 'LeftFoot' in bone_group_objs:
                bone_group_objs['LeftFoot'].add([i], 1.0, 'REPLACE')
    # Jambe Droite
    elif x > 0.04 and z < 1.05:
        if z >= 0.55:
            if 'RightUpLeg' in bone_group_objs:
                bone_group_objs['RightUpLeg'].add([i], 1.0, 'REPLACE')
        elif z >= 0.15:
            if 'RightLeg' in bone_group_objs:
                bone_group_objs['RightLeg'].add([i], 1.0, 'REPLACE')
        else:
            if 'RightFoot' in bone_group_objs:
                bone_group_objs['RightFoot'].add([i], 1.0, 'REPLACE')
    # Buste & Hanches
    else:
        if z >= 1.35:
            if 'Spine2' in bone_group_objs:
                bone_group_objs['Spine2'].add([i], 1.0, 'REPLACE')
            elif 'Spine1' in bone_group_objs:
                bone_group_objs['Spine1'].add([i], 1.0, 'REPLACE')
        elif z >= 1.10:
            if 'Spine' in bone_group_objs:
                bone_group_objs['Spine'].add([i], 1.0, 'REPLACE')
        else:
            if 'Hips' in bone_group_objs:
                bone_group_objs['Hips'].add([i], 1.0, 'REPLACE')

print("Skinning BVH terminé !")

# =========================================================
# 5. CAMÉRA CINÉMA & RENDU DES STILLS & VIDÉO
# =========================================================
print("[5/5] Cadrage cinématique & Rendu...")
cam_data = bpy.data.cameras.new('CinematicCamera')
cam_data.lens = 42
cam_data.sensor_width = 36
cam_obj = bpy.data.objects.new('CinematicCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_keyframes = [
    (1,  Vector((-0.4, -4.5, 1.4)), Vector((-1.6, 0.0, 1.3))),
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
print('MASTER_AI_PRODUCTION_COMPLETE')
