import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb")
obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

print("Inspecting Face/Forehead Polygons by Height:")
for z_thresh in [0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82]:
    front_polys = []
    for poly in obj.data.polygons:
        p_verts = [obj.matrix_world @ obj.data.vertices[vi].co for vi in poly.vertices]
        avg_z = sum(v.z for v in p_verts) / len(p_verts)
        avg_y = sum(v.y for v in p_verts) / len(p_verts)
        avg_x = sum(v.x for v in p_verts) / len(p_verts)
        if abs(avg_z - z_thresh) < 0.01 and avg_y < 0.0 and abs(avg_x) < 0.12:
            front_polys.append((avg_x, avg_y, avg_z))
    print(f"Z ~ {z_thresh:.2f}: {len(front_polys)} front face polygons (avg_y ~ {sum(p[1] for p in front_polys)/max(1, len(front_polys)):.3f})")
