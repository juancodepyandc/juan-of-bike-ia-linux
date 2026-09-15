import bpy
import os
import sys
import math
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/avatar_femelle_vizion_raw.glb"
OUT_DIR = "/home/juan/AuroraIA/application/output/3d/avatar_femelle_vizion_renders"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)

# Cycles GPU setup
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'CUDA'
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024

# Studio World Lighting
world = bpy.data.worlds.new("StudioWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.045, 0.048, 0.055, 1.0)
bg.inputs["Strength"].default_value = 0.85

# Import GLB
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

mesh_objs = [o for o in scene.objects if o.type == 'MESH']
if not mesh_objs:
    print("NO_MESH_FOUND")
    sys.exit(1)

main_obj = max(mesh_objs, key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
main_obj.select_set(True)
bpy.context.view_layer.objects.active = main_obj

# Center and calculate bounding box
verts = [main_obj.matrix_world @ v.co for v in main_obj.data.vertices]
min_v = Vector(map(min, *verts))
max_v = Vector(map(max, *verts))
center = (min_v + max_v) * 0.5
size = max_v - min_v
max_dim = max(size.x, size.y, size.z)

# 3-Point Studio Lighting
key_light = bpy.data.objects.new("KeyLight", bpy.data.lights.new("KeyLight", type='AREA'))
key_light.data.energy = 450.0
key_light.data.size = 2.0
key_light.data.color = (1.0, 0.95, 0.90)
key_light.location = center + Vector((1.8, -2.8, 1.8))
key_light.rotation_euler = (math.radians(55), 0, math.radians(28))
scene.collection.objects.link(key_light)

fill_light = bpy.data.objects.new("FillLight", bpy.data.lights.new("FillLight", type='AREA'))
fill_light.data.energy = 180.0
fill_light.data.size = 2.5
fill_light.data.color = (0.85, 0.92, 1.0)
fill_light.location = center + Vector((-2.2, -2.2, 1.2))
fill_light.rotation_euler = (math.radians(60), 0, math.radians(-42))
scene.collection.objects.link(fill_light)

rim_light = bpy.data.objects.new("RimLight", bpy.data.lights.new("RimLight", type='AREA'))
rim_light.data.energy = 380.0
rim_light.data.size = 2.0
rim_light.data.color = (1.0, 0.88, 0.75)
rim_light.location = center + Vector((0.0, 2.5, 2.2))
rim_light.rotation_euler = (math.radians(125), 0, 0)
scene.collection.objects.link(rim_light)

cam_data = bpy.data.cameras.new("RenderCam")
cam_data.lens = 55
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

def render_view(cam_pos, look_at, out_name):
    cam_obj.location = cam_pos
    fwd = (look_at - cam_pos).normalized()
    cam_obj.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(OUT_DIR, out_name)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_name}")

dist_full = max_dim * 1.55

# 1. Front View
render_view(center + Vector((0, -dist_full, 0.05 * max_dim)), center + Vector((0, 0, 0.05 * max_dim)), "vue_femelle_front.png")

# 2. Back View
render_view(center + Vector((0, dist_full, 0.05 * max_dim)), center + Vector((0, 0, 0.05 * max_dim)), "vue_femelle_back.png")

# 3. 3/4 Front-Left View
render_view(center + Vector((-dist_full * 0.75, -dist_full * 0.75, 0.1 * max_dim)), center + Vector((0, 0, 0.05 * max_dim)), "vue_femelle_front_left.png")

# 4. 3/4 Front-Right View
render_view(center + Vector((dist_full * 0.75, -dist_full * 0.75, 0.1 * max_dim)), center + Vector((0, 0, 0.05 * max_dim)), "vue_femelle_front_right.png")

# 5. Zoom Head & Hair
head_center = center + Vector((0, 0, size.z * 0.35))
render_view(head_center + Vector((0, -size.z * 0.52, 0.02)), head_center, "zoom_femelle_face_hair.png")

# 6. Zoom T-Shirt Design
torso_center = center + Vector((0, 0, size.z * 0.08))
render_view(torso_center + Vector((0, -size.z * 0.55, 0.0)), torso_center, "zoom_femelle_tshirt.png")

print("ALL_FEMALE_AVATAR_RENDERS_COMPLETED_SUCCESSFULLY!")
