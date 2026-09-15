
import bpy, sys
argv = sys.argv[sys.argv.index("--") + 1:]
glb_path, out_png = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 28
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720

w = bpy.data.worlds.new('StudioWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.05, 0.06, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 0.8

sun_data = bpy.data.lights.new('Sun', type='SUN')
sun_data.energy = 4.0
sun_data.color = (1.0, 0.98, 0.94)
sun_obj = bpy.data.objects.new('Sun', sun_data)
sun_obj.rotation_euler = (0.85, 0.3, -0.6)
scene.collection.objects.link(sun_obj)

rim_data = bpy.data.lights.new('Rim', type='POINT')
rim_data.energy = 500.0
rim_data.color = (0.6, 0.85, 1.0)
rim_obj = bpy.data.objects.new('Rim', rim_data)
rim_obj.location = (-3.5, 3.5, 3.5)
scene.collection.objects.link(rim_obj)

bpy.ops.import_scene.gltf(filepath=glb_path)

cam_data = bpy.data.cameras.new('Camera')
cam_data.lens = 45
cam_obj = bpy.data.objects.new('Camera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.location = (0, -2.8, 1.1)
cam_obj.rotation_euler = (1.28, 0, 0)

scene.render.filepath = out_png
bpy.ops.render.render(write_still=True)
