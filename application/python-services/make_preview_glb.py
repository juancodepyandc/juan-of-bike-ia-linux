import bpy
import os
import sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
src, dst = argv[0], argv[1]
budget = int(argv[2]) if len(argv) > 2 else 200000

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

for o in bpy.context.scene.objects:
    if o.type != "MESH":
        continue
    if o.data.shape_keys is not None:
        continue
    n = len(o.data.polygons)
    if n > budget:
        dec = o.modifiers.new("dec", "DECIMATE")
        dec.ratio = budget / float(n)
        with bpy.context.temp_override(object=o, active_object=o, selected_editable_objects=[o]):
            bpy.ops.object.modifier_apply(modifier=dec.name)

for img in bpy.data.images:
    if img.size[0] > 2048:
        img.scale(2048, 2048)

os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB",
                          export_animations=True, export_skins=True,
                          export_yup=True, export_image_format="JPEG")
print("PREVIEW_OK:" + dst)
