import bpy
import bmesh
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(obj.data)

# Find vertices on the hard hairline ridge (0.76 < z < 0.81, y < -0.12, abs(x) < 0.14)
# Smooth their Y coordinate to create a soft, natural forehead curve
ridge_verts = []
for v in bm.verts:
    if 0.755 < v.co.z < 0.810 and v.co.y < -0.10 and abs(v.co.x) < 0.15:
        ridge_verts.append(v)
        # Soften outward protrusion
        t = (v.co.z - 0.755) / (0.810 - 0.755)
        # Pull Y slightly back towards head center
        v.co.y = v.co.y * (1.0 - 0.12 * math.sin(t * math.pi)) + (-0.11) * (0.12 * math.sin(t * math.pi))

print(f"Smoothed {len(ridge_verts)} hairline ridge vertices!")
bm.to_mesh(obj.data)
bm.free()
obj.data.update()
