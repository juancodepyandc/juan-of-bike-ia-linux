import bpy
import math
import os
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"
OUT_DIR = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 64
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.film_transparent = False

# Neutral studio background
world = bpy.data.worlds.new("StudioWorld")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.045, 0.048, 0.056, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# 3-Point Studio Lighting with warm key light
# Key Light (Warm soft 5500K)
key_light = bpy.data.lights.new(name="KeyLight", type='AREA')
key_light.energy = 160.0
key_light.size = 2.0
key_light.color = (1.0, 0.96, 0.92)
key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_light)
key_obj.location = Vector((1.2, -2.2, 1.5))
bpy.context.collection.objects.link(key_obj)

# Fill Light (Cool soft fill)
fill_light = bpy.data.lights.new(name="FillLight", type='AREA')
fill_light.energy = 90.0
fill_light.size = 3.0
fill_light.color = (0.92, 0.96, 1.0)
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_light)
fill_obj.location = Vector((-1.6, -1.8, 1.2))
bpy.context.collection.objects.link(fill_obj)

# Rim Light (Crisp edge highlight)
rim_light = bpy.data.lights.new(name="RimLight", type='AREA')
rim_light.energy = 140.0
rim_light.size = 2.0
rim_light.color = (1.0, 1.0, 1.0)
rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_light)
rim_obj.location = Vector((0.0, 2.0, 1.8))
bpy.context.collection.objects.link(rim_obj)

# Head Soft Light
head_light = bpy.data.lights.new(name="HeadLight", type='AREA')
head_light.energy = 70.0
head_light.size = 1.2
head_light.color = (1.0, 0.97, 0.94)
head_obj = bpy.data.objects.new(name="HeadLight", object_data=head_light)
head_obj.location = Vector((0.0, -1.8, 1.6))
bpy.context.collection.objects.link(head_obj)

# Camera
cam_data = bpy.data.cameras.new("RenderCam")
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
scene.camera = cam_obj

views = [
    ("vue_final_front.png", Vector((0.0, -2.5, 0.15)), Vector((0.0, 0.0, 0.10)), 50),
    ("vue_final_back.png", Vector((0.0, 2.5, 0.15)), Vector((0.0, 0.0, 0.10)), 50),
    ("vue_final_left.png", Vector((-2.5, 0.0, 0.15)), Vector((0.0, 0.0, 0.10)), 50),
    ("vue_final_right.png", Vector((2.5, 0.0, 0.15)), Vector((0.0, 0.0, 0.10)), 50),
    ("zoom_front_details.png", Vector((0.0, -1.25, 0.12)), Vector((0.0, 0.0, 0.12)), 65),
    ("zoom_back_details.png", Vector((0.0, 1.25, 0.12)), Vector((0.0, 0.0, 0.12)), 65),
    ("zoom_head_details.png", Vector((0.0, -1.0, 0.65)), Vector((0.0, 0.0, 0.65)), 75),
    ("zoom_hand_left_5f.png", Vector((0.64, -0.75, 0.28)), Vector((0.64, 0.0, 0.28)), 90),
]

for filename, pos, target, lens in views:
    cam_obj.location = pos
    cam_data.lens = lens
    
    # Point at target
    direction = target - pos
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()
    
    scene.render.filepath = os.path.join(OUT_DIR, filename)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {filename}")

print("ALL RENDERS COMPLETED SUCCESSFULLY!")
