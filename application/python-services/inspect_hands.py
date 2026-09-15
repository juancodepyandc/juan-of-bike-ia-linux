import bpy
import numpy as np

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

# Let's inspect the hand bounding boxes (extremities of X)
verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
xs = [v.x for v in verts]
min_x, max_x = min(xs), max(xs)

# Left hand (positive X) and Right hand (negative X)
left_hand_verts = [v for v in verts if v.x > max_x - 0.25]
right_hand_verts = [v for v in verts if v.x < min_x + 0.25]

print(f"X range: {min_x:.3f} to {max_x:.3f}")
print(f"Left hand vertex count: {len(left_hand_verts)}, Right hand vertex count: {len(right_hand_verts)}")
