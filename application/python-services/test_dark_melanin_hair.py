import bpy

OUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=OUT_GLB)

for mat in bpy.data.materials:
    if "Hair" in mat.name:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Pure dark chocolate melanin hair
            bsdf.inputs["Base Color"].default_value = (0.003, 0.002, 0.001, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.90
            if "IOR" in bsdf.inputs:
                bsdf.inputs["IOR"].default_value = 1.33
            if "Specular IOR Level" in bsdf.inputs:
                bsdf.inputs["Specular IOR Level"].default_value = 0.03
            elif "Specular" in bsdf.inputs:
                bsdf.inputs["Specular"].default_value = 0.03
            if "Sheen Weight" in bsdf.inputs:
                bsdf.inputs["Sheen Weight"].default_value = 0.0
            if "Subsurface Weight" in bsdf.inputs:
                bsdf.inputs["Subsurface Weight"].default_value = 0.0

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)
print("SUCCESS: Set melanin dark afro hair!")
