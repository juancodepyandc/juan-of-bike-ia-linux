import bpy
import bmesh

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(ob.data)
uv_bm = bm.loops.layers.uv.verify()

# Collect UVs for forehead vertices (0.65 < z < 0.72, y < 0.05, |x| < 0.15)
forehead_uvs = []
for face in bm.faces:
    for loop in face.loops:
        v = loop.vert
        if 0.65 < v.co.z < 0.72 and v.co.y < 0.05 and abs(v.co.x) < 0.15:
            uv = loop[uv_bm].uv
            forehead_uvs.append((uv.x, uv.y))

bm.free()

u_coords = [u[0] for u in forehead_uvs]
v_coords = [u[1] for u in forehead_uvs]
print(f"Forehead UV Range: U=[{min(u_coords):.3f}, {max(u_coords):.3f}], V=[{min(v_coords):.3f}, {max(v_coords):.3f}]")

