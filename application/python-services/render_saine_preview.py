import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/_sauvegarde_vizion/personnage_texture_saine.glb")

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.render.resolution_x = 768
scene.render.resolution_y = 768

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

cam.location = (0, -2.4, 0.1)
cam.rotation_euler = (1.5708, 0, 0)

world = bpy.data.worlds.new("World")
scene.world = world
world.color = (0.05, 0.05, 0.05)

light_data = bpy.data.lights.new(name="Sun", type='SUN')
light_data.energy = 4.0
light = bpy.data.objects.new(name="Sun", object_data=light_data)
scene.collection.objects.link(light)
light.rotation_euler = (0.785, 0.3, 0.5)

scene.render.filepath = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/preview_saine.png"
bpy.ops.render.render(write_still=True)
print("Rendered preview_saine.png")
