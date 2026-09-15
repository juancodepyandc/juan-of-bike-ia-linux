import bpy
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
ORIG_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
OUT_IMG = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_orig_render.png"

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

world = bpy.data.worlds.new("StudioWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.045, 0.048, 0.055, 1.0)
bg.inputs["Strength"].default_value = 0.85

bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
main_obj = max([o for o in scene.objects if o.type == 'MESH'], key=lambda o: len(o.data.polygons))

verts = [main_obj.matrix_world @ v.co for v in main_obj.data.vertices]
min_v = Vector(map(min, *verts))
max_v = Vector(map(max, *verts))
center = (min_v + max_v) * 0.5
size = max_v - min_v

# Lighting
key_light = bpy.data.objects.new("KeyLight", bpy.data.lights.new("KeyLight", type='AREA'))
key_light.data.energy = 450.0
key_light.data.size = 2.0
key_light.data.color = (1.0, 0.95, 0.90)
key_light.location = center + Vector((1.8, -2.8, 1.8))
scene.collection.objects.link(key_light)

fill_light = bpy.data.objects.new("FillLight", bpy.data.lights.new("FillLight", type='AREA'))
fill_light.data.energy = 180.0
fill_light.data.size = 2.5
fill_light.data.color = (0.85, 0.92, 1.0)
fill_light.location = center + Vector((-2.2, -2.2, 1.2))
scene.collection.objects.link(fill_light)

rim_light = bpy.data.objects.new("RimLight", bpy.data.lights.new("RimLight", type='AREA'))
rim_light.data.energy = 380.0
rim_light.data.size = 2.0
rim_light.data.color = (1.0, 0.88, 0.75)
rim_light.location = center + Vector((0.0, 2.5, 2.2))
scene.collection.objects.link(rim_light)

head_center = center + Vector((0, 0, size.z * 0.38))
cam_data = bpy.data.cameras.new("RenderCam")
cam_data.lens = 65
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_obj.location = head_center + Vector((0, -size.z * 0.52, 0.02))
fwd = (head_center - cam_obj.location).normalized()
cam_obj.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()

# Apply orig texture to material
mat = main_obj.data.materials[0]
for node in mat.node_tree.nodes:
    if node.type == 'TEX_IMAGE':
        node.image = bpy.data.images.load(ORIG_TEX)

scene.render.filepath = OUT_IMG
bpy.ops.render.render(write_still=True)
print("SUCCESS_TEST_ORIG_RENDER_SAVED!")
