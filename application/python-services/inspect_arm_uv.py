import bpy
import bmesh

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
mesh = ob.data

bm = bmesh.new()
bm.from_mesh(mesh)
uv_bm = bm.loops.layers.uv.verify()

arm_l_uvs = []
arm_r_uvs = []
for face in bm.faces:
    for loop in face.loops:
        if 0.50 < loop.vert.co.x < 0.60:
            uv = loop[uv_bm].uv
            arm_l_uvs.append((uv.x, uv.y))
        elif -0.60 < loop.vert.co.x < -0.50:
            uv = loop[uv_bm].uv
            arm_r_uvs.append((uv.x, uv.y))

bm.free()

print(f"Left arm sample UV: {arm_l_uvs[0]}")
print(f"Right arm sample UV: {arm_r_uvs[0]}")
