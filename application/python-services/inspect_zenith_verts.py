import bpy
import bmesh
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
mesh = ob.data

bm = bmesh.new()
bm.from_mesh(mesh)
uv_bm = bm.loops.layers.uv.verify()

count = 0
for face in bm.faces:
    for loop in face.loops:
        vz = loop.vert.co.z
        if vz > 0.90: # Top hair apex
            loop[uv_bm].uv = Vector((0.120, 0.136))
            count += 1

print(f"Directly remapped {count} loops at z > 0.90 to espresso curls swatch!")
bm.to_mesh(mesh)
bm.free()
mesh.update()

bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    export_apply=True
)
