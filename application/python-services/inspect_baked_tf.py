import bpy

# Let's save baked_tshirt_f directly
INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
FRONT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

cam = bpy.data.objects.new("CamTest", bpy.data.cameras.new("CamTest"))
cam.location = (0, -3.0, 0.15)
cam.rotation_euler = (1.5707963, 0, 0)
bpy.context.scene.collection.objects.link(cam)

baked_img = bpy.data.images.new("BakedImg", 4096, 4096)

mat = bpy.data.materials.new("Mat")
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()

n_out = nodes.new("ShaderNodeOutputMaterial")
n_emit = nodes.new("ShaderNodeEmission")
n_img = nodes.new("ShaderNodeTexImage")
n_img.image = bpy.data.images.load(FRONT_TEX)
n_img.extension = 'CLIP'

n_tc = nodes.new("ShaderNodeTexCoord")
n_tc.object = cam

n_map = nodes.new("ShaderNodeMapping")
n_map.vector_type = "POINT"
# Camera local coords: X goes from -0.3 to +0.3, Y goes from -0.3 to +0.3
# We want U = X / scale + 0.5, V = Y / scale + 0.5
n_map.inputs["Location"].default_value = (0.5, 0.5, 0.0)
n_map.inputs["Scale"].default_value = (1.0 / 0.54, 1.0 / 0.54, 1.0)

mat.node_tree.links.new(n_tc.outputs["Object"], n_map.inputs["Vector"])
mat.node_tree.links.new(n_map.outputs["Vector"], n_img.inputs["Vector"])
mat.node_tree.links.new(n_img.outputs["Color"], n_emit.inputs["Color"])
mat.node_tree.links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])

n_target = nodes.new("ShaderNodeTexImage")
n_target.image = baked_img
nodes.active = n_target
ob.active_material = mat

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.ops.object.bake(type='EMIT')

baked_img.filepath_raw = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_baked_tf.png"
baked_img.file_format = 'PNG'
baked_img.save()
print("Saved test_baked_tf.png")
