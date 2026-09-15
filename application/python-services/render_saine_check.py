import bpy
import math
import os
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/_sauvegarde_vizion/personnage_texture_saine.glb"
OUT_FILE = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/saine_check.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024

# Camera
cam_data = bpy.data.cameras.new("RenderCam")
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.location = Vector((0.0, -2.5, 0.15))
cam_data.lens = 50

# Light
light = bpy.data.lights.new(name="Light", type='AREA')
light.energy = 200.0
light.size = 2.0
l_obj = bpy.data.objects.new(name="Light", object_data=light)
l_obj.location = Vector((1.0, -2.0, 1.5))
bpy.context.collection.objects.link(l_obj)

# Point at target
direction = Vector((0.0, 0.0, 0.10)) - cam_obj.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

scene.render.filepath = OUT_FILE
bpy.ops.render.render(write_still=True)
print(f"Rendered: {OUT_FILE}")
