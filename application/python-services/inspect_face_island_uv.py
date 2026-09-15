import bpy
import numpy as np

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb")
obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

uv_layer = obj.data.uv_layers.active.data
face_loops = []
for poly in obj.data.polygons:
    p_verts = [obj.matrix_world @ obj.data.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    avg_y = sum(v.y for v in p_verts) / len(p_verts)
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    # Head & face region
    if avg_z > 0.48 and avg_y < 0.05 and abs(avg_x) < 0.20:
        for li in poly.loop_indices:
            uv = uv_layer[li].uv
            face_loops.append((uv.x, uv.y, avg_x, avg_y, avg_z))

print(f"Total face loop vertices: {len(face_loops)}")
if face_loops:
    min_u = min(f[0] for f in face_loops)
    max_u = max(f[0] for f in face_loops)
    min_v = min(f[1] for f in face_loops)
    max_v = max(f[1] for f in face_loops)
    print(f"Face UV region in 4K texture: U=[{min_u:.4f}, {max_u:.4f}], V=[{min_v:.4f}, {max_v:.4f}]")
