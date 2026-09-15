import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb")

for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f"Mesh: {obj.name}, verts={len(obj.data.vertices)}, polys={len(obj.data.polygons)}")

for img in bpy.data.images:
    print(f"Image: {img.name}, size={img.size}")
    if img.size[0] > 0:
        img.filepath_raw = f"/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/source_{img.name}.png"
        img.file_format = 'PNG'
        img.save()
        print(f"Saved source_{img.name}.png")
