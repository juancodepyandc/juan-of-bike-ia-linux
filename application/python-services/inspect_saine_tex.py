import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/_sauvegarde_vizion/personnage_texture_saine.glb")

for img in bpy.data.images:
    print(f"Image: {img.name}, Size: {img.size}")
    if img.size[0] > 0:
        img.filepath_raw = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/extracted_saine_texture.png"
        img.file_format = 'PNG'
        img.save()
        print("Saved extracted_saine_texture.png!")
