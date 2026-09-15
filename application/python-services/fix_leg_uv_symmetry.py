import bpy
import bmesh
from mathutils import Vector, kdtree

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

bm = bmesh.new()
bm.from_mesh(ob.data)
uv_bm = bm.loops.layers.uv.verify()

# Build KD-tree of right-side vertices (x > 0) on the legs (-0.65 < z < 0.05)
right_verts = [v for v in bm.verts if v.co.x > 0.01 and -0.65 < v.co.z < 0.05]
kd = kdtree.KDTree(len(right_verts))
for i, v in enumerate(right_verts):
    kd.insert(v.co, i)
kd.balance()

# Map left leg vertices to the right leg's clean UVs
for face in bm.faces:
    for loop in face.loops:
        v = loop.vert
        if v.co.x < -0.005 and -0.65 < v.co.z < 0.05:
            # Symmetrical position on right side
            sym_co = Vector((-v.co.x, v.co.y, v.co.z))
            co, index, dist = kd.find(sym_co)
            if dist < 0.03:
                r_vert = right_verts[index]
                # Find UV of r_vert in its loops
                for r_loop in r_vert.link_loops:
                    r_uv = r_loop[uv_bm].uv
                    # If right UV is a valid jeans UV (not modified)
                    if r_uv.x != 0.500 or r_uv.y != 0.100:
                        loop[uv_bm].uv = r_uv
                        break

bm.to_mesh(ob.data)
bm.free()
ob.data.update()

bpy.ops.export_scene.gltf(
    filepath=INPUT_GLB,
    export_format='GLB',
    export_apply=True
)
print("SUCCESS: Mirrored right leg clean denim UVs to left leg!")
