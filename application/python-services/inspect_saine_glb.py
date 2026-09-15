import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/_sauvegarde_vizion/personnage_texture_saine.glb")

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
print(f"Saine Mesh: {ob.name}, Polys={len(ob.data.polygons)}, Verts={len(ob.data.vertices)}")
print("UV Layers:", [uv.name for uv in ob.data.uv_layers])
print("Materials:", [m.name for m in ob.data.materials])
