import bpy
import bmesh
import json
import sys
import os

def audit_mesh(glb_path, out_json):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    try:
        bpy.ops.import_scene.gltf(filepath=glb_path)
    except Exception as e:
        with open(out_json, 'w') as f: json.dump({"error": f"Import failed: {e}"}, f)
        return
        
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        with open(out_json, 'w') as f: json.dump({"error": "No mesh found"}, f)
        return

    bpy.context.view_layer.objects.active = meshes[0]
    for obj in meshes: obj.select_set(True)
    if len(meshes) > 1: bpy.ops.object.join()
    obj = bpy.context.active_object
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    
    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
    degenerated_faces = sum(1 for f in bm.faces if f.calc_area() < 1e-6)
    
    # Internal faces check (heuristic: faces with all vertices inside the bounding volume, or just rely on non-manifold)
    # pymeshlab is usually better for internal faces, but we track degenerated & manifold here.
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Floaters (Loose parts)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    parts = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    
    report = {
        "is_manifold": non_manifold_edges == 0,
        "non_manifold_edges": non_manifold_edges,
        "degenerated_faces": degenerated_faces,
        "parts_count": len(parts),
        "total_faces": sum(len(p.data.polygons) for p in parts)
    }
    
    with open(out_json, 'w') as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        audit_mesh(args[0], args[1])
