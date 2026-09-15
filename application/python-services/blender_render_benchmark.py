"""Blender Cycles render script for benchmark dragon model.
Usage: blender --background --python blender_render_benchmark.py
"""
import bpy
import math
import os
import sys

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/benchmark_ultimate_complex_model/raw_model.glb"
RENDER_DIR = "/home/juan/AuroraIA/application/output/3d/benchmark_ultimate_complex_model/renders"
os.makedirs(RENDER_DIR, exist_ok=True)

# --- Clean scene ---
bpy.ops.wm.read_factory_settings(use_empty=True)

# --- Import GLB ---
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

# --- Center and normalize ---
imported = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not imported:
    print("ERROR: No mesh imported!")
    sys.exit(1)

# Select all meshes and join
bpy.ops.object.select_all(action='DESELECT')
for o in imported:
    o.select_set(True)
bpy.context.view_layer.objects.active = imported[0]
if len(imported) > 1:
    bpy.ops.object.join()

obj = bpy.context.active_object

# Center origin
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
obj.location = (0, 0, 0)

# Normalize scale to fit in a 2-unit cube
bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
if bbox:
    import mathutils
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    max_dim = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    if max_dim > 0:
        scale = 2.0 / max_dim
        obj.scale = (scale, scale, scale)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        obj.location = (0, 0, 0)

# --- Render settings ---
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 256
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'

# GPU compute
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    prefs.preferences.compute_device_type = 'CUDA'
    prefs.preferences.get_devices()
    for d in prefs.preferences.devices:
        d.use = True

# --- World background: neutral studio grey ---
world = bpy.data.worlds.new("StudioWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.15, 0.15, 0.15, 1.0)
    bg.inputs[1].default_value = 0.8

# --- Lighting: 3-point studio ---
def add_area_light(name, location, rotation, energy, size=2.0):
    bpy.ops.object.light_add(type='AREA', location=location, rotation=rotation)
    light = bpy.context.active_object
    light.name = name
    light.data.energy = energy
    light.data.size = size
    return light

# Key light (front-right, above)
add_area_light("Key", (3, -3, 4), (math.radians(45), 0, math.radians(45)), 500, 3.0)
# Fill light (front-left, lower)
add_area_light("Fill", (-3, -2, 2), (math.radians(30), 0, math.radians(-30)), 200, 2.5)
# Rim light (behind, above)
add_area_light("Rim", (0, 4, 5), (math.radians(-50), 0, 0), 350, 2.0)

# --- Camera ---
cam_data = bpy.data.cameras.new("RenderCam")
cam_data.lens = 50
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

CAMERA_DISTANCE = 3.5

# --- Render views ---
views = {
    "render_front": (0, -CAMERA_DISTANCE, 0.5),
    "render_back": (0, CAMERA_DISTANCE, 0.5),
    "render_3quarter": (CAMERA_DISTANCE * 0.7, -CAMERA_DISTANCE * 0.7, 0.8),
}

for view_name, cam_loc in views.items():
    cam_obj.location = cam_loc
    # Point camera at origin
    direction = mathutils.Vector((0, 0, 0)) - mathutils.Vector(cam_loc)
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()
    
    scene.render.filepath = os.path.join(RENDER_DIR, view_name + ".png")
    bpy.ops.render.render(write_still=True)
    print(f"[OK] Rendered {view_name}")

print("[DONE] All renders complete!")
