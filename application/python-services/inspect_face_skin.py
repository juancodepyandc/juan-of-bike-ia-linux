import bpy
import bmesh
import numpy as np

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(ob.data)
uv_bm = bm.loops.layers.uv.verify()

# Find UV coordinates of facial vertices (nose, cheeks, chin)
face_uvs = []
for f in bm.faces:
    fc = f.calc_center_median()
    # Face center is around z in [0.55, 0.75], y < -0.05, abs(x) < 0.15
    if 0.55 <= fc.z <= 0.75 and fc.y < -0.05 and abs(fc.x) < 0.12:
        for loop in f.loops:
            face_uvs.append(loop[uv_bm].uv)

print(f"Sampled {len(face_uvs)} face UV coordinates")
avg_u = sum(uv.x for uv in face_uvs) / len(face_uvs)
avg_v = sum(uv.y for uv in face_uvs) / len(face_uvs)
print(f"Face UV center: U={avg_u:.4f}, V={avg_v:.4f}")

# Sample pixels from texture around face UV center
img = bpy.data.images.load(BASE_TEX)
w, h = img.size
pixels = np.array(img.pixels[:]).reshape((h, w, 4))

fu, fv = int(avg_u * w), int(avg_v * h)
sample = pixels[fv-10:fv+10, fu-10:fu+10, :3]
mean_col = sample.mean(axis=(0, 1))
print(f"Face average RGB in texture: R={mean_col[0]:.3f}, G={mean_col[1]:.3f}, B={mean_col[2]:.3f}")

bm.free()
