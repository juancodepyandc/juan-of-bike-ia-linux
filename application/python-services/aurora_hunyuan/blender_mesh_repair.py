import bpy
import sys

def repair_mesh(glb_path, out_glb_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        return

    bpy.context.view_layer.objects.active = meshes[0]
    for obj in meshes: obj.select_set(True)
    if len(meshes) > 1: bpy.ops.object.join()
    obj = bpy.context.active_object
    
    # Keep only the largest component (delete floaters)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    parts = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    parts.sort(key=lambda p: len(p.data.polygons), reverse=True)
    
    # Delete all parts except the largest
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts[1:]:
        p.select_set(True)
    if len(parts) > 1:
        bpy.ops.object.delete()
        
    main_obj = parts[0]
    bpy.context.view_layer.objects.active = main_obj
    main_obj.select_set(True)
    
    # 1. Weld Modifier (Merge by Distance in C++)
    weld_mod = main_obj.modifiers.new(name="Weld", type="WELD")
    weld_mod.merge_threshold = 0.0001
    bpy.ops.object.modifier_apply(modifier=weld_mod.name)
    
    # 2. Decimate Modifier
    faces = len(main_obj.data.polygons)
    if faces > 150000:
        ratio = 150000.0 / faces
        dec_mod = main_obj.modifiers.new(name='Decimate', type='DECIMATE')
        dec_mod.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=dec_mod.name)
        
    # 3. Clean degenerated faces in Edit Mode
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.dissolve_degenerate()
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Export
    bpy.ops.export_scene.gltf(filepath=out_glb_path, export_format='GLB', use_selection=True)

if __name__ == "__main__":
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        repair_mesh(args[0], args[1])
