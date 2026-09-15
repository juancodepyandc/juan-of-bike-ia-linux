import bpy
import math
import os
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
OUT_DIR = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
ob = bpy.context.active_object
bpy.ops.object.shade_smooth()

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

# Simple Caramel PBR Shader for all geometry
mat = bpy.data.materials.new(name="CaramelMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.75, 0.45, 0.28, 1.0)
bsdf.inputs["Roughness"].default_value = 0.5
ob.data.materials.clear()
ob.data.materials.append(mat)

# Studio Lighting
world = bpy.data.worlds.new("StudioWorld")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.05, 0.05, 0.07, 1.0)
bg.inputs["Strength"].default_value = 0.8

cam_data = bpy.data.cameras.new("Cam")
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

light = bpy.data.objects.new("Light", bpy.data.lights.new("Light", type='AREA'))
light.data.energy = 400
light.data.size = 2.0
bpy.context.scene.collection.objects.link(light)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024

# Left hand zoom
hand_lx = mx.x - 0.08
hand_lz = center.z + size.z * 0.18
cam_obj.location = (hand_lx, center.y - 0.60, hand_lz)
cam_obj.rotation_euler = (math.radians(90), 0, 0)
cam_data.lens = 70
light.location = (hand_lx, center.y - 0.60, hand_lz + 0.2)

bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "zoom_hand_5finger_left.png")
bpy.ops.render.render(write_still=True)
print("Rendered: zoom_hand_5finger_left.png")

# Right hand zoom
hand_rx = mn.x + 0.08
cam_obj.location = (hand_rx, center.y - 0.60, hand_lz)
cam_obj.rotation_euler = (math.radians(90), 0, 0)
light.location = (hand_rx, center.y - 0.60, hand_lz + 0.2)

bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "zoom_hand_5finger_right.png")
bpy.ops.render.render(write_still=True)
print("Rendered: zoom_hand_5finger_right.png")
