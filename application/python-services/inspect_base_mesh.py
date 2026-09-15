import bpy
import bmesh

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
print("Base mesh vertices:", len(ob.data.vertices))
print("Base mesh polygons:", len(ob.data.polygons))

bm = bmesh.new()
bm.from_mesh(ob.data)
boundary_edges = [e for e in bm.edges if e.is_boundary]
print("Base mesh boundary edges:", len(boundary_edges))
bm.free()
