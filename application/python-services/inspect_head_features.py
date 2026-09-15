import bpy
import bmesh
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(ob.data)
uv_bm = bm.loops.layers.uv.verify()

# Check UVs of face vertices
for f in bm.faces:
    fc = f.calc_center_median()
    # If face is in nose/mouth/eye front zone:
    if 0.58 <= fc.z <= 0.72 and fc.y < -0.06 and abs(fc.x) < 0.08:
        uvs = [l[uv_bm].uv for l in f.loops]
        u_avg = sum(u.x for u in uvs)/len(uvs)
        v_avg = sum(u.y for u in uvs)/len(uvs)

print("Face front zone UV centers:")
bm.free()
