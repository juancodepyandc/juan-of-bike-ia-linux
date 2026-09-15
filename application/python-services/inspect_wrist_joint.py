import bpy
import bmesh
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

print("Total vertices:", len(ob.data.vertices))
print("Total polygons:", len(ob.data.polygons))

# Check connected components (islands)
bm = bmesh.new()
bm.from_mesh(ob.data)

# Find boundary edges (open edges where mesh was cut)
boundary_edges = [e for e in bm.edges if e.is_boundary]
print("Boundary open edges:", len(boundary_edges))
boundary_verts = set()
for e in boundary_edges:
    boundary_verts.add(e.verts[0])
    boundary_verts.add(e.verts[1])
print("Boundary open vertices:", len(boundary_verts))
for v in list(boundary_verts)[:10]:
    print("  boundary vert co:", v.co)

bm.free()
