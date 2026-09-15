import bpy
import numpy as np

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb")
obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

uv_layer = obj.data.uv_layers.active.data
nose_uvs = []
eyes_uvs = []
chin_uvs = []
ears_uvs = []

for poly in obj.data.polygons:
    p_verts = [obj.matrix_world @ obj.data.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    avg_y = sum(v.y for v in p_verts) / len(p_verts)
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    
    # Nose (z ~ 0.58, y < -0.15, abs(x) < 0.04)
    if 0.54 < avg_z < 0.62 and avg_y < -0.14 and abs(avg_x) < 0.04:
        for li in poly.loop_indices:
            nose_uvs.append(uv_layer[li].uv)
            
    # Eyes (z ~ 0.64, y < -0.12, abs(x) < 0.08)
    if 0.62 < avg_z < 0.68 and avg_y < -0.10 and 0.02 < abs(avg_x) < 0.08:
        for li in poly.loop_indices:
            eyes_uvs.append(uv_layer[li].uv)
            
    # Chin (z ~ 0.49, y < -0.08, abs(x) < 0.04)
    if 0.47 < avg_z < 0.52 and avg_y < -0.06 and abs(avg_x) < 0.04:
        for li in poly.loop_indices:
            chin_uvs.append(uv_layer[li].uv)
            
    # Ears (z ~ 0.60, abs(x) > 0.16)
    if 0.55 < avg_z < 0.65 and abs(avg_x) > 0.16:
        for li in poly.loop_indices:
            ears_uvs.append(uv_layer[li].uv)

def print_box(name, uvs):
    if uvs:
        u_min = min(uv.x for uv in uvs)
        u_max = max(uv.x for uv in uvs)
        v_min = min(uv.y for uv in uvs)
        v_max = max(uv.y for uv in uvs)
        print(f"{name} UV Box: U=[{u_min:.3f}, {u_max:.3f}], V=[{v_min:.3f}, {v_max:.3f}] (Center: U={(u_min+u_max)/2:.3f}, V={(v_min+v_max)/2:.3f})")

print_box("Nose", nose_uvs)
print_box("Eyes", eyes_uvs)
print_box("Chin", chin_uvs)
print_box("Ears", ears_uvs)
