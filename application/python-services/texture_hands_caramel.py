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

for face in bm.faces:
    for loop in face.loops:
        vx = loop.vert.co.x
        if vx > 0.54:
            # Left Hand & Wrist -> exact left arm caramel skin swatch
            loop[uv_bm].uv = Vector((0.3655, 0.8289))
        elif vx < -0.54:
            # Right Hand & Wrist -> exact right arm caramel skin swatch
            loop[uv_bm].uv = Vector((0.7817, 0.5153))

bm.to_mesh(mesh)
bm.free()
mesh.update()

bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    export_apply=True
)
print("Updated Hand & Wrist UVs to exact left/right arm caramel skin swatches!")
