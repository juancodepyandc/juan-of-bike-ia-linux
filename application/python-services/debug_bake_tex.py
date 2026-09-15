import bpy

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
mat = ob.data.materials[0]
tex = mat.node_tree.nodes.get("Image Texture").image
tex.filepath_raw = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/debug_exported_tex.png"
tex.file_format = 'PNG'
tex.save()
print("Saved debug_exported_tex.png")
