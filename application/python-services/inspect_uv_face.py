import bpy
import numpy as np

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb")
obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

uv_layer = obj.data.uv_layers.active.data
uvs = [uv_layer[li].uv for li in range(len(obj.data.loops))]
min_u = min(uv.x for uv in uvs)
max_u = max(uv.x for uv in uvs)
min_v = min(uv.y for uv in uvs)
max_v = max(uv.y for uv in uvs)

print(f"Overall UV Bounds: U=[{min_u:.3f}, {max_u:.3f}], V=[{min_v:.3f}, {max_v:.3f}]")

# Find face UVs (vertices with z > 0.5 and y < 0)
face_uvs = []
for poly in obj.data.polygons:
    p_verts = [obj.matrix_world @ obj.data.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    avg_y = sum(v.y for v in p_verts) / len(p_verts)
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    if avg_z > 0.50 and avg_y < 0.04 and abs(avg_x) < 0.15:
        for li in poly.loop_indices:
            face_uvs.append(uv_layer[li].uv)

if face_uvs:
    print(f"Face UV Bounds: U=[{min(uv.x for uv in face_uvs):.3f}, {max(uv.x for uv in face_uvs):.3f}], V=[{min(uv.y for uv in face_uvs):.3f}, {max(uv.y for uv in face_uvs):.3f}]")
