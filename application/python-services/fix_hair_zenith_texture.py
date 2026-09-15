import bpy
import bmesh
import numpy as np

TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
mesh = ob.data

bm = bmesh.new()
bm.from_mesh(mesh)
uv_bm = bm.loops.layers.uv.verify()

img = bpy.data.images.load(TEX_PATH)
w, h = img.size
pixels = np.array(img.pixels[:]).reshape((h, w, 4))

hair_fixed_count = 0
for face in bm.faces:
    for loop in face.loops:
        v = loop.vert.co
        if v.z > 0.80:
            uv = loop[uv_bm].uv
            px = int(uv.x * w) % w
            py = int(uv.y * h) % h
            
            c = pixels[py, px]
            if c[0] > 0.35 and c[1] > 0.35 and c[2] > 0.35:
                # Set to espresso hair color
                y_min = max(0, py - 4)
                y_max = min(h, py + 5)
                x_min = max(0, px - 4)
                x_max = min(w, px + 5)
                
                pixels[y_min:y_max, x_min:x_max, 0] = 0.08  # R
                pixels[y_min:y_max, x_min:x_max, 1] = 0.05  # G
                pixels[y_min:y_max, x_min:x_max, 2] = 0.04  # B
                pixels[y_min:y_max, x_min:x_max, 3] = 1.0   # A
                hair_fixed_count += 1

bm.free()

img.pixels = pixels.ravel()
img.filepath_raw = TEX_PATH
img.file_format = 'PNG'
img.save()

print(f"Fixed {hair_fixed_count} hair zenith pixels on 4K base texture!")
