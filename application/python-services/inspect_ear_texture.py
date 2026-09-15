import bpy
import numpy as np
from PIL import Image

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
body = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

uv_layer = body.data.uv_layers.active.data
tex_im = Image.open(TEX_PATH).convert("RGBA")
w, h = tex_im.size
arr = np.array(tex_im)

ear_uvs = []
for poly in body.data.polygons:
    p_verts = [body.matrix_world @ body.data.vertices[vi].co for vi in poly.vertices]
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    if abs(avg_x) > 0.15 and 0.54 < avg_z < 0.74:
        for loop_idx in poly.loop_indices:
            uv = uv_layer[loop_idx].uv
            ear_uvs.append(uv)

print(f"Total UV samples for ears: {len(ear_uvs)}")
if ear_uvs:
    u_vals = [uv.x for uv in ear_uvs]
    v_vals = [uv.y for uv in ear_uvs]
    print(f"U range: {min(u_vals):.4f} to {max(u_vals):.4f}")
    print(f"V range: {min(v_vals):.4f} to {max(v_vals):.4f}")

    # Sample pixel colors in this UV bounding box
    min_px_u = int(min(u_vals) * w)
    max_px_u = int(max(u_vals) * w)
    min_px_v = int((1.0 - max(v_vals)) * h)
    max_px_v = int((1.0 - min(v_vals)) * h)
    
    print(f"Pixel box: X=[{min_px_u}:{max_px_u}], Y=[{min_px_v}:{max_px_v}]")
