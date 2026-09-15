import bpy
import math
from mathutils import Vector, Euler

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Create test bone and mesh
arm_data = bpy.data.armatures.new('TestArm')
arm_obj = bpy.data.objects.new('TestArm', arm_data)
scene.collection.objects.link(arm_obj)

bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='EDIT')
b = arm_data.edit_bones.new('Leg')
b.head = (0, 0, 1); b.tail = (0, 0, 0)
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.5))
mesh_obj = bpy.context.active_object

mesh_obj.parent = arm_obj
mod = mesh_obj.modifiers.new('Armature', 'ARMATURE')
mod.object = arm_obj

vg = mesh_obj.vertex_groups.new(name='Leg')
vg.add(list(range(len(mesh_obj.data.vertices))), 1.0, 'REPLACE')

# Set animation
arm_obj.animation_data_create()
act = bpy.data.actions.new('TestMotion')
arm_obj.animation_data.action = act

pb = arm_obj.pose.bones['Leg']
pb.rotation_mode = 'XYZ'

# Frame 1: 0 deg
pb.rotation_euler.x = 0
pb.keyframe_insert(data_path='rotation_euler', frame=1)

# Frame 10: 90 deg
pb.rotation_euler.x = math.radians(90)
pb.keyframe_insert(data_path='rotation_euler', frame=10)

# Check evaluated mesh positions
scene.frame_set(1)
depsgraph1 = bpy.context.evaluated_depsgraph_get()
eval_mesh1 = mesh_obj.evaluated_get(depsgraph1)
v1 = eval_mesh1.data.vertices[0].co.copy()

scene.frame_set(10)
depsgraph10 = bpy.context.evaluated_depsgraph_get()
eval_mesh10 = mesh_obj.evaluated_get(depsgraph10)
v10 = eval_mesh10.data.vertices[0].co.copy()

delta = (v10 - v1).length
print(f"VERIFICATION RESULT: Vertex 0 moved by {delta:.4f} meters from frame 1 to 10!")
if delta > 0.1:
    print("SUCCESS: Blender 5.1 Pose Bone Euler animation deform is 100% OPERATIONAL!")
else:
    print("FAILED: Mesh did not deform!")
