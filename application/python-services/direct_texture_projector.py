import bpy
import bmesh
import numpy as np
from mathutils import Vector

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
BASE_TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
FRONT_TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
BACK_TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
OUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
mesh = ob.data

img_base = bpy.data.images.load(BASE_TEX_PATH)
img_f = bpy.data.images.load(FRONT_TEX_PATH)
img_b = bpy.data.images.load(BACK_TEX_PATH)

w, h = img_base.size
base_arr = np.array(img_base.pixels[:]).reshape((h, w, 4))
f_arr = np.array(img_f.pixels[:]).reshape((h, w, 4))
b_arr = np.array(img_b.pixels[:]).reshape((h, w, 4))

verts = [ob.matrix_world @ v.co for v in mesh.vertices]
zs = [v.z for v in verts]
center_z = (min(zs) + max(zs)) * 0.5
size_z = max(zs) - min(zs)
torso_z = center_z + size_z * 0.08
ortho_s = 0.54

bm = bmesh.new()
bm.from_mesh(mesh)
uv_bm = bm.loops.layers.uv.verify()

# For each face on torso, map its UV polygon from Front or Back texture!
for face in bm.faces:
    avg_co = sum((face.verts[i].co for i in range(len(face.verts))), Vector((0,0,0))) / len(face.verts)
    n = face.normal
    
    # Check if face is on Torso (-0.18 < z < 0.42 and abs(x) < 0.32)
    if -0.18 < avg_co.z < 0.42 and abs(avg_co.x) < 0.32:
        is_front = (avg_co.y < 0.02) and (n.y < 0.25)
        is_back = (avg_co.y > -0.02) and (n.y > -0.25)
        
        for loop in face.loops:
            uv = loop[uv_bm].uv
            pu = int(uv.x * w) % w
            pv = int(uv.y * h) % h
            
            vx, vy, vz = loop.vert.co.x, loop.vert.co.y, loop.vert.co.z
            
            if is_front:
                u_proj = vx / ortho_s + 0.5
                v_proj = (vz - torso_z) / ortho_s + 0.5
                if 0.0 <= u_proj <= 1.0 and 0.0 <= v_proj <= 1.0:
                    src_px = int(u_proj * w) % w
                    src_py = int(v_proj * h) % h
                    # Paint 3x3 kernel around UV pixel to ensure zero seam gap!
                    base_arr[max(0, pv-1):min(h, pv+2), max(0, pu-1):min(w, pu+2)] = f_arr[src_py, src_px]
            elif is_back:
                u_proj = -vx / ortho_s + 0.5
                v_proj = (vz - torso_z) / ortho_s + 0.5
                if 0.0 <= u_proj <= 1.0 and 0.0 <= v_proj <= 1.0:
                    src_px = int(u_proj * w) % w
                    src_py = int(v_proj * h) % h
                    base_arr[max(0, pv-1):min(h, pv+2), max(0, pu-1):min(w, pu+2)] = b_arr[src_py, src_px]

bm.free()

final_img = bpy.data.images.new("MasterCompositeTex4K", width=w, height=h)
final_img.pixels = base_arr.ravel()

# PBR Material
mat = bpy.data.materials.new(name="MasterPBR")
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()

out_n = nodes.new("ShaderNodeOutputMaterial")
bsdf_n = nodes.new("ShaderNodeBsdfPrincipled")
tex_n = nodes.new("ShaderNodeTexImage")
tex_n.image = final_img
bsdf_n.inputs["Roughness"].default_value = 0.48
bsdf_n.inputs["Metallic"].default_value = 0.0

mat.node_tree.links.new(tex_n.outputs["Color"], bsdf_n.inputs["Base Color"])
mat.node_tree.links.new(bsdf_n.outputs["BSDF"], out_n.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)

print(f"\nSUCCESS_DIRECT_PROJECTED_GLB: {OUT_GLB}\n")
