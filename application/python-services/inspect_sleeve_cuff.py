import bpy
import math

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

verts = [v.co for v in body_obj.data.vertices if 0.33 <= v.co.x <= 0.36]
y_vals = [v.y for v in verts]
z_vals = [v.z for v in verts]

cy = sum(y_vals) / len(y_vals)
cz = sum(z_vals) / len(z_vals)

radii = [math.sqrt((v.y - cy)**2 + (v.z - cz)**2) for v in verts]
print(f"Sleeve cuff at x=0.34: center=({cy:.4f}, {cz:.4f}), avg_r={sum(radii)/len(radii):.4f}")
