
import bpy, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, p_front, p_back = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 28
scene.cycles.use_denoising = True
scene.render.resolution_x = 1024
scene.render.resolution_y = 768

w = bpy.data.worlds.new('Studio')
scene.world = w
w.use_nodes = True
w.node_tree.nodes.get('Background').inputs['Color'].default_value = (0.06, 0.07, 0.09, 1.0)

sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', type='SUN'))
sun.data.energy = 4.2
sun.rotation_euler = (0.85, 0.3, -0.6)
scene.collection.objects.link(sun)

fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', type='SUN'))
fill.data.energy = 2.2
fill.rotation_euler = (0.85, 0.3, 2.5)
scene.collection.objects.link(fill)

bpy.ops.import_scene.gltf(filepath=glb_in)

cam_obj = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
cam_obj.data.lens = 42
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Rendu 1 : Face 3/4
cam_p1 = Vector((1.8, -2.8, 1.6))
cam_obj.location = cam_p1
cam_obj.rotation_euler = (Vector((0,0,0.5)) - cam_p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = p_front
bpy.ops.render.render(write_still=True)

# Rendu 2 : Dos 3/4
cam_p2 = Vector((-1.8, 2.8, 1.6))
cam_obj.location = cam_p2
cam_obj.rotation_euler = (Vector((0,0,0.5)) - cam_p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = p_back
bpy.ops.render.render(write_still=True)
print('ISO_RENDERS_DONE')
