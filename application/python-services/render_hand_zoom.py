import bpy
import math
import os
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"
OUT_DIR = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

# Studio Lighting
world = bpy.data.worlds.new("StudioWorld")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.05, 0.05, 0.07, 1.0)
bg.inputs["Strength"].default_value = 0.9

cam_data = bpy.data.cameras.new("HandCam")
cam_obj = bpy.data.objects.new("HandCam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

headlight = bpy.data.objects.new("HeadLight", bpy.data.lights.new("HeadLight", type='AREA'))
headlight.data.energy = 450
headlight.data.size = 2.0
bpy.context.scene.collection.objects.link(headlight)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024

# Left hand (positive X)
hand_lx = mx.x - 0.12
hand_lz = center.z + size.z * 0.18
cam_obj.location = (hand_lx, center.y - 0.70, hand_lz)
cam_obj.rotation_euler = (math.radians(90), 0, 0)
cam_data.lens = 70
headlight.location = (hand_lx, center.y - 0.70, hand_lz + 0.2)

bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "zoom_hand_left.png")
bpy.ops.render.render(write_still=True)
print("Rendered: zoom_hand_left.png")

# Right hand (negative X)
hand_rx = mn.x + 0.12
cam_obj.location = (hand_rx, center.y - 0.70, hand_lz)
cam_obj.rotation_euler = (math.radians(90), 0, 0)
headlight.location = (hand_rx, center.y - 0.70, hand_lz + 0.2)

bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "zoom_hand_right.png")
bpy.ops.render.render(write_still=True)
print("Rendered: zoom_hand_right.png")
