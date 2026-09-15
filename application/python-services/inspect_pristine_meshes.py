import bpy

for path in [
    "/home/juan/AuroraIA/application/output/3d/_sauvegarde_vizion/personnage_texture_saine.glb",
    "/home/juan/AuroraIA/application/output/3d/vizion_studio/personnage/personnage_mesh.glb",
]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    print(f"=== {path} ===")
    print(f"Objects: {[o.name for o in objs]}")
    for img in bpy.data.images:
        print(f"  Image: {img.name}, size: {img.size[0]}x{img.size[1]}")
