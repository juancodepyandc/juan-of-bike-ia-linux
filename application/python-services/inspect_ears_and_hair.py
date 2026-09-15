import bpy
import bmesh
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

# Find ear coordinates
ear_polys = []
for p in body.data.polygons:
    p_verts = [body.matrix_world @ body.data.vertices[vi].co for vi in p.vertices]
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    avg_y = sum(v.y for v in p_verts) / len(p_verts)
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    # Ear region: x ~ 0.16 to 0.26, z ~ 0.54 to 0.72
    if abs(avg_x) > 0.16 and 0.54 < avg_z < 0.72:
        ear_polys.append((avg_x, avg_y, avg_z, p.normal.y))

print(f"Total ear polygons in range: {len(ear_polys)}")
if ear_polys:
    min_y = min(p[1] for p in ear_polys)
    max_y = max(p[1] for p in ear_polys)
    min_z = min(p[2] for p in ear_polys)
    max_z = max(p[2] for p in ear_polys)
    print(f"Ear Y range: {min_y:.3f} to {max_y:.3f}")
    print(f"Ear Z range: {min_z:.3f} to {max_z:.3f}")
