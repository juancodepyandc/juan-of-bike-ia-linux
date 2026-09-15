import bpy
import numpy as np

TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
mesh = ob.data

img = bpy.data.images.load(TEX_PATH)
w, h = img.size
pixels = np.array(img.pixels[:]).reshape((h, w, 4))

uv_layer = mesh.uv_layers.active.data
bm_faces = mesh.polygons

for poly in mesh.polygons:
    # Check if polygon is on torso (-0.18 < z < 0.40 and abs(x) < 0.32)
    poly_verts = [mesh.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in poly_verts) / len(poly_verts)
    avg_x = sum(v.x for v in poly_verts) / len(poly_verts)
    
    if -0.18 < avg_z < 0.42 and abs(avg_x) < 0.32:
        for loop_idx in poly.loop_indices:
            uv = uv_layer[loop_idx].uv
            px = int(uv.x * w) % w
            py = int(uv.y * h) % h
            
            y_min = max(0, py - 4)
            y_max = min(h, py + 5)
            x_min = max(0, px - 4)
            x_max = min(w, px + 5)
            
            pixels[y_min:y_max, x_min:x_max, 0] = 0.045  # R
            pixels[y_min:y_max, x_min:x_max, 1] = 0.045  # G
            pixels[y_min:y_max, x_min:x_max, 2] = 0.050  # B
            pixels[y_min:y_max, x_min:x_max, 3] = 1.0

img.pixels = pixels.ravel()
img.filepath_raw = TEX_PATH
img.file_format = 'PNG'
img.save()
print("Cleaned base torso to 100% pure matte black!")
