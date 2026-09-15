import bpy
import bmesh
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

verts = [v.co for v in body_obj.data.vertices if 0.53 <= v.co.x <= 0.56]
y_vals = [v.y for v in verts]
z_vals = [v.z for v in verts]

cy = sum(y_vals) / len(y_vals)
cz = sum(z_vals) / len(z_vals)

radii = [math.sqrt((v.y - cy)**2 + (v.z - cz)**2) for v in verts]
avg_r = sum(radii) / len(radii)
max_r = max(radii)
min_r = min(radii)

print(f"Forearm at x=0.55: center=({cy:.4f}, {cz:.4f}), avg_r={avg_r:.4f}, min_r={min_r:.4f}, max_r={max_r:.4f}")
