import bpy

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)
body = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

uv_layer = body.data.uv_layers.active.data
ear_uvs = []
for poly in body.data.polygons:
    p_verts = [body.matrix_world @ body.data.vertices[vi].co for vi in poly.vertices]
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    if abs(avg_x) > 0.15 and 0.54 < avg_z < 0.74:
        for loop_idx in poly.loop_indices:
            uv = uv_layer[loop_idx].uv
            ear_uvs.append((uv.x, uv.y))

u_vals = [uv[0] for uv in ear_uvs]
v_vals = [uv[1] for uv in ear_uvs]
print(f"Total UV samples for ears: {len(ear_uvs)}")
print(f"U range: {min(u_vals):.4f} to {max(u_vals):.4f}")
print(f"V range: {min(v_vals):.4f} to {max(v_vals):.4f}")
