
# --- Garde d execution -----------------------------------------------------
# Ce fichier est un scenario BLENDER : il ne tourne que dans l interpreteur
# embarque de Blender, ou `bpy` existe. Sous `unittest discover`, son import
# levait ModuleNotFoundError et comptait comme une ERREUR de test — sept
# fichiers rendaient ainsi la suite Python durablement rouge, ce qui masque
# les vraies regressions. On declare desormais un SAUT explicite : la suite
# rapporte « ignore », qui est la verite, au lieu d une erreur.
import unittest as _unittest_guard
try:
    import bpy as _bpy_guard  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - hors Blender
    raise _unittest_guard.SkipTest(
        "scenario Blender : necessite l interpreteur bpy (lancer via blender --python)")
# ---------------------------------------------------------------------------
import bpy
import math
import os
from mathutils import Vector, Euler

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.render.resolution_x = 960
scene.render.resolution_y = 540

# Import Creature GLB
CREATURE_RAW_GLB = '/home/juan/AuroraIA/application/output/3d/living_creature_scene/creature_raw.glb'
bpy.ops.import_scene.gltf(filepath=CREATURE_RAW_GLB)
mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]

dec = mesh.modifiers.new('Dec', 'DECIMATE')
dec.ratio = 0.04
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.modifier_apply(modifier='Dec')

mesh.scale = Vector((2.1, 2.1, 2.1))
bpy.ops.object.transform_apply(scale=True)

# Build matched Armature in rest pose
arm_data = bpy.data.armatures.new('Arm')
arm_obj = bpy.data.objects.new('Arm', arm_data)
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

# Tail
tail1 = eb.new('Tail.01')
tail1.head = (0, -0.20, 0.05); tail1.tail = (0, -0.55, 0.0); tail1.parent = pelvis

tail2 = eb.new('Tail.02')
tail2.head = (0, -0.55, 0.0); tail2.tail = (0, -0.95, 0.25); tail2.parent = tail1

# Legs
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

# Arms
upper_arm_l = eb.new('UpperArm.L')
upper_arm_l.head = (-0.45, 0, 0.95); upper_arm_l.tail = (-0.80, 0, 0.55); upper_arm_l.parent = chest

forearm_l = eb.new('Forearm.L')
forearm_l.head = (-0.80, 0, 0.55); forearm_l.tail = (-0.85, 0.08, 0.10); forearm_l.parent = upper_arm_l

upper_arm_r = eb.new('UpperArm.R')
upper_arm_r.head = (0.45, 0, 0.95); upper_arm_r.tail = (0.80, 0, 0.55); upper_arm_r.parent = chest

forearm_r = eb.new('Forearm.R')
forearm_r.head = (0.80, 0, 0.55); forearm_r.tail = (0.85, 0.08, 0.10); forearm_r.parent = upper_arm_r

bpy.ops.object.mode_set(mode='OBJECT')

mesh.parent = arm_obj
mod = mesh.modifiers.new('Armature', 'ARMATURE')
mod.object = arm_obj
mod.use_vertex_groups = True

bone_names = ['Root', 'Pelvis', 'Spine', 'Chest', 'Neck', 'Head', 
              'Thigh.L', 'Shin.L', 'Foot.L', 'Thigh.R', 'Shin.R', 'Foot.R',
              'UpperArm.L', 'Forearm.L', 'UpperArm.R', 'Forearm.R', 'Tail.01', 'Tail.02']

vgs = {name: mesh.vertex_groups.new(name=name) for name in bone_names}

for i, v in enumerate(mesh.data.vertices):
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

print('Rigged successfully! Testing stair climbing gait...')

# Add rich stair climbing animation
arm_obj.animation_data_create()
act = bpy.data.actions.new('StairClimb')
arm_obj.animation_data.action = act

bpy.ops.object.mode_set(mode='POSE')
pb = arm_obj.pose.bones

# Total 72 frames: 4 full steps of stair climb
# Step 1: Right leg (f 1 to 18)
# Step 2: Left leg (f 19 to 36)
# Step 3: Right leg (f 37 to 54)
# Step 4: Left leg onto landing & Roar (f 55 to 72)

STEP_H = 0.17
STEP_L = 0.36
START_X = -1.5
Z_OFF = 1.05

for f in range(1, 73):
    # Determine phase
    t_global = (f - 1) / 71.0
    
    # Root position
    if f <= 18:
        # Step 1: Right leg leads
        p = (f - 1) / 17.0
        x = START_X + p * STEP_L
        z = Z_OFF + p * STEP_H
        rot_z = 55 - p * 3
        # Right leg swings up
        pb['Thigh.R'].rotation_euler.x = math.radians(-50 * math.sin(p * math.pi))
        pb['Shin.R'].rotation_euler.x = math.radians(75 * math.sin(p * math.pi))
        pb['Foot.R'].rotation_euler.x = math.radians(-20 * math.sin(p * math.pi))
        # Left leg pushes
        pb['Thigh.L'].rotation_euler.x = math.radians(15 * p)
        pb['Shin.L'].rotation_euler.x = math.radians(-5 * p)
        # Arm swing
        pb['UpperArm.L'].rotation_euler.x = math.radians(-25 * math.sin(p * math.pi))
        pb['UpperArm.R'].rotation_euler.x = math.radians(25 * math.sin(p * math.pi))
    elif f <= 36:
        # Step 2: Left leg leads
        p = (f - 19) / 17.0
        x = START_X + STEP_L + p * STEP_L
        z = Z_OFF + STEP_H + p * STEP_H
        rot_z = 52 - p * 4
        # Left leg swings up
        pb['Thigh.L'].rotation_euler.x = math.radians(-55 * math.sin(p * math.pi))
        pb['Shin.L'].rotation_euler.x = math.radians(80 * math.sin(p * math.pi))
        pb['Foot.L'].rotation_euler.x = math.radians(-20 * math.sin(p * math.pi))
        # Right leg pushes
        pb['Thigh.R'].rotation_euler.x = math.radians(15 * p)
        pb['Shin.R'].rotation_euler.x = math.radians(-5 * p)
        # Arm swing
        pb['UpperArm.R'].rotation_euler.x = math.radians(-30 * math.sin(p * math.pi))
        pb['UpperArm.L'].rotation_euler.x = math.radians(30 * math.sin(p * math.pi))
    elif f <= 54:
        # Step 3: Right leg leads
        p = (f - 37) / 17.0
        x = START_X + 2 * STEP_L + p * STEP_L
        z = Z_OFF + 2 * STEP_H + p * STEP_H
        rot_z = 48 - p * 5
        pb['Thigh.R'].rotation_euler.x = math.radians(-50 * math.sin(p * math.pi))
        pb['Shin.R'].rotation_euler.x = math.radians(75 * math.sin(p * math.pi))
        pb['Foot.R'].rotation_euler.x = math.radians(-20 * math.sin(p * math.pi))
        pb['Thigh.L'].rotation_euler.x = math.radians(15 * p)
        pb['Shin.L'].rotation_euler.x = math.radians(-5 * p)
        pb['UpperArm.L'].rotation_euler.x = math.radians(-25 * math.sin(p * math.pi))
        pb['UpperArm.R'].rotation_euler.x = math.radians(25 * math.sin(p * math.pi))
    else:
        # Arrival on landing + Heroic Roar
        p = (f - 55) / 17.0
        x = START_X + 3 * STEP_L + p * 0.8
        z = Z_OFF + 4 * STEP_H
        rot_z = 43 - p * 23  # Turns face to camera (20 deg)
        pb['Thigh.L'].rotation_euler.x = math.radians(5 * (1 - p))
        pb['Shin.L'].rotation_euler.x = 0
        pb['Thigh.R'].rotation_euler.x = math.radians(5 * (1 - p))
        pb['Shin.R'].rotation_euler.x = 0
        # Roar posture
        pb['Spine'].rotation_euler.x = math.radians(-12 * p)
        pb['Head'].rotation_euler.x = math.radians(15 * p)
        pb['UpperArm.L'].rotation_euler = Euler((math.radians(-20 * p), math.radians(15 * p), math.radians(30 * p)))
        pb['UpperArm.R'].rotation_euler = Euler((math.radians(-20 * p), math.radians(-15 * p), math.radians(-30 * p)))
        pb['Tail.01'].rotation_euler = Euler((math.radians(25 * p), math.radians(10 * p), 0))
        pb['Tail.02'].rotation_euler = Euler((math.radians(45 * p), 0, 0))
    
    # Spine natural counter-twist during locomotion
    if f < 55:
        pb['Spine'].rotation_euler.z = math.radians(6 * math.sin((f / 18.0) * math.pi))
        pb['Spine'].rotation_euler.x = math.radians(12)  # Natural forward lean while climbing stairs
        pb['Tail.01'].rotation_euler.y = math.radians(15 * math.sin((f / 18.0) * math.pi))

    # Insert keyframes
    arm_obj.location = Vector((x, 0, z))
    arm_obj.rotation_euler.z = math.radians(rot_z)
    arm_obj.keyframe_insert(data_path='location', frame=f)
    arm_obj.keyframe_insert(data_path='rotation_euler', frame=f)
    for b in pb:
        b.keyframe_insert(data_path='rotation_euler', frame=f)

bpy.ops.object.mode_set(mode='OBJECT')
print('Continuous gait cycle keyframed for all 72 frames!')
