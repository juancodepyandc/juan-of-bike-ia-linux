import bpy
import bmesh
import numpy as np

BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bm = bmesh.new()
bm.from_mesh(ob.data)
uv_bm = bm.loops.layers.uv.verify()

regions = {
    "Head/Face": lambda co: co.z > 0.50 and abs(co.x) < 0.20,
    "Nose/Cheeks": lambda co: 0.55 <= co.z <= 0.72 and co.y < -0.06 and abs(co.x) < 0.10,
    "Neck": lambda co: 0.40 <= co.z <= 0.52 and abs(co.x) < 0.12,
    "Legs/Jeans": lambda co: -0.65 <= co.z <= 0.00,
    "Shoes": lambda co: co.z < -0.65,
}

for name, filter_fn in regions.items():
    uvs = []
    for f in bm.faces:
        fc = f.calc_center_median()
        if filter_fn(fc):
            for loop in f.loops:
                uvs.append((loop[uv_bm].uv.x, loop[uv_bm].uv.y))
    if uvs:
        u_arr = np.array([u[0] for u in uvs])
        v_arr = np.array([u[1] for u in uvs])
        print(f"Region: {name:15s} | count={len(uvs):6d} | U: [{u_arr.min():.3f}, {u_arr.max():.3f}] avg={u_arr.mean():.3f} | V: [{v_arr.min():.3f}, {v_arr.max():.3f}] avg={v_arr.mean():.3f}")

bm.free()
