import bpy
import bmesh
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(ob.data)

print(f"Total verts: {len(bm.verts)}")
# Chin / mouth: z approx?
# Forehead: z approx?
# Hair top: z approx?

verts_z = [v.co.z for v in bm.verts]
print(f"Min Z: {min(verts_z):.3f}, Max Z: {max(verts_z):.3f}")

# Neck verts
neck_verts = [v.co for v in bm.verts if 0.40 < v.co.z < 0.55 and abs(v.co.x) < 0.15]
print(f"Neck count: {len(neck_verts)}")

# Forehead / Eyes verts
face_verts = [v.co for v in bm.verts if 0.55 <= v.co.z <= 0.74 and abs(v.co.x) < 0.22 and v.co.y < 0.08]
print(f"Face front count: {len(face_verts)}")

bm.free()
