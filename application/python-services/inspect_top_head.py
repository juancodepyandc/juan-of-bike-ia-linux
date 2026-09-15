import bpy
import bmesh
import numpy as np

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"
TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

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

white_spots = []
for face in bm.faces:
    for loop in face.loops:
        if loop.vert.co.z > 0.80:
            uv = loop[uv_bm].uv
            px = int(uv.x * w) % w
            py = int(uv.y * h) % h
            r, g, b, a = pixels[py, px]
            if r > 0.60 and g > 0.60 and b > 0.60:
                white_spots.append((loop.vert.co.x, loop.vert.co.y, loop.vert.co.z, uv.x, uv.y, (r, g, b)))

bm.free()
print(f"Found {len(white_spots)} white/untextured loops on top of head (Z > 0.80)!")
if white_spots:
    for i in range(min(5, len(white_spots))):
        print(f"Sample: co=({white_spots[i][0]:.3f}, {white_spots[i][1]:.3f}, {white_spots[i][2]:.3f}), UV=({white_spots[i][3]:.4f}, {white_spots[i][4]:.4f}), RGB=({white_spots[i][5][0]:.2f}, {white_spots[i][5][1]:.2f}, {white_spots[i][5][2]:.2f})")
