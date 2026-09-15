import bpy
import bmesh
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(body_obj.data)
uv_bm = bm.loops.layers.uv.verify()

sleeve_faces = []
for f in bm.faces:
    # check if face center is in sleeve region
    fc = f.calc_center_median()
    if 0.28 <= fc.x <= 0.42:
        # Check UV of first loop
        uv = f.loops[0][uv_bm].uv
        sleeve_faces.append((fc, uv))

print(f"Total faces in sleeve region: {len(sleeve_faces)}")
for fc, uv in sleeve_faces[::100]:
    print(f"  x={fc.x:.3f}, y={fc.y:.3f}, z={fc.z:.3f} -> UV=({uv.x:.3f}, {uv.y:.3f})")

bm.free()
