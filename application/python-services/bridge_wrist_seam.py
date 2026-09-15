import bpy
import bmesh

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(ob.data)

# Find boundary edges (edges with only 1 face)
boundary_edges = [e for e in bm.edges if e.is_boundary]
print(f"Found {len(boundary_edges)} boundary edges.")

# Fill boundary holes
bmesh.ops.holes_fill(bm, edges=boundary_edges)

bm.to_mesh(ob.data)
bm.free()
ob.data.update()

bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    export_apply=True
)
print(f"Exported watertight 5-finger mesh: {GLB_PATH}")
