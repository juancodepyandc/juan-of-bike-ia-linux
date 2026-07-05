"""
Aurora Scene Builder (Layer 3)
Blender headless script that imports all generated objects based on scene_manifest.json,
places them, scales them, and applies animations.
"""
import bpy
import json
import sys
import os
from mathutils import Vector

def _parse_args() -> tuple[str, str]:
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        args = sys.argv[idx + 1 :]
    else:
        args = sys.argv[1:]
    if len(args) < 2:
        raise SystemExit("usage: blender --background --python aurora_scene_builder.py -- <manifest.json> <out_dir>")
    return args[0], args[1]

def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)

def import_and_place(glb_path: str, pos: list[float], scale: list[float]) -> bpy.types.Object:
    if not os.path.exists(glb_path):
        print(f"Skipping {glb_path}: File not found")
        return None
        
    bpy.ops.import_scene.gltf(filepath=glb_path)
    meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not meshes:
        return None
        
    obj = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        
    obj.location = Vector(pos)
    obj.scale = Vector(scale)
    return obj

def build_scene(manifest_path: str, out_dir: str):
    reset_scene()
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    base_dir = os.path.dirname(manifest_path)
    
    for obj_data in manifest.get("objects", []):
        obj_id = obj_data.get("id")
        pos = obj_data.get("position", [0, 0, 0])
        scale = obj_data.get("scale", [1, 1, 1])
        # Expected GLB path from Layer 2
        glb_path = os.path.join(base_dir, f"pbr_{obj_id}_pack", "model.glb")
        
        imported_obj = import_and_place(glb_path, pos, scale)
        if imported_obj:
            imported_obj.name = obj_id
            print(f"Placed {obj_id} at {pos}")
            
    # Export final scene
    out_glb = os.path.join(out_dir, "scene_assembled.glb")
    bpy.ops.export_scene.gltf(
        filepath=out_glb,
        export_format="GLB",
        use_selection=False,
        export_animations=True,
        export_apply=True
    )
    print(f"Assembled scene exported to {out_glb}")

if __name__ == "__main__":
    manifest_path, out_dir = _parse_args()
    try:
        build_scene(manifest_path, out_dir)
    except Exception as e:
        print(f"Scene Builder failed: {e}")
        sys.exit(1)
