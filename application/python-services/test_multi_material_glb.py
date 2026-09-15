import bpy
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
FRONT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
BACK_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
OUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active = ob

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn
torso_z = center.z + size.z * 0.08
ortho_s = 0.44

# Setup Cameras for UV Projection
cam_f = bpy.data.objects.new("CamProjF", bpy.data.cameras.new("CamProjF"))
cam_f.data.type = 'ORTHO'
cam_f.data.ortho_scale = ortho_s
cam_f.location = Vector((center.x, center.y - 2.0, torso_z + 0.02))
cam_f.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_f)

cam_b = bpy.data.objects.new("CamProjB", bpy.data.cameras.new("CamProjB"))
cam_b.data.type = 'ORTHO'
cam_b.data.ortho_scale = ortho_s
cam_b.location = Vector((center.x, center.y + 2.0, torso_z + 0.02))
cam_b.rotation_euler = (math.pi / 2.0, 0, math.pi)
bpy.context.scene.collection.objects.link(cam_b)

uv_front = ob.data.uv_layers.new(name="UV_Front")
mod_f = ob.modifiers.new("UVProjF", 'UV_PROJECT')
mod_f.uv_layer = "UV_Front"
mod_f.projector_count = 1
mod_f.projectors[0].object = cam_f
bpy.ops.object.modifier_apply(modifier="UVProjF")

uv_back = ob.data.uv_layers.new(name="UV_Back")
mod_b = ob.modifiers.new("UVProjB", 'UV_PROJECT')
mod_b.uv_layer = "UV_Back"
mod_b.projector_count = 1
mod_b.projectors[0].object = cam_b
bpy.ops.object.modifier_apply(modifier="UVProjB")

# Material 1: Character Body Base (Face, Hair, Skin, Jeans, Shoes)
mat_body = bpy.data.materials.new(name="Material_Body")
mat_body.use_nodes = True
n_b = mat_body.node_tree.nodes
n_b.clear()
out_b = n_b.new("ShaderNodeOutputMaterial")
bsdf_b = n_b.new("ShaderNodeBsdfPrincipled")
tex_b_img = n_b.new("ShaderNodeTexImage")
tex_b_img.image = bpy.data.images.load(BASE_TEX)
bsdf_b.inputs["Roughness"].default_value = 0.46
mat_body.node_tree.links.new(tex_b_img.outputs["Color"], bsdf_b.inputs["Base Color"])
mat_body.node_tree.links.new(bsdf_b.outputs["BSDF"], out_b.inputs["Surface"])

# Material 2: Front Decal PBR
mat_front = bpy.data.materials.new(name="Material_Front_Graphic")
mat_front.use_nodes = True
n_f = mat_front.node_tree.nodes
n_f.clear()
out_f = n_f.new("ShaderNodeOutputMaterial")
bsdf_f = n_f.new("ShaderNodeBsdfPrincipled")
tex_f_img = n_f.new("ShaderNodeTexImage")
tex_f_img.image = bpy.data.images.load(FRONT_TEX)
tex_f_img.extension = 'CLIP'
uv_f_node = n_f.new("ShaderNodeUVMap")
uv_f_node.uv_map = "UV_Front"
bsdf_f.inputs["Roughness"].default_value = 0.48
mat_front.node_tree.links.new(uv_f_node.outputs["UV"], tex_f_img.inputs["Vector"])
mat_front.node_tree.links.new(tex_f_img.outputs["Color"], bsdf_f.inputs["Base Color"])
mat_front.node_tree.links.new(bsdf_f.outputs["BSDF"], out_f.inputs["Surface"])

# Material 3: Back Decal PBR
mat_back = bpy.data.materials.new(name="Material_Back_Graphic")
mat_back.use_nodes = True
n_k = mat_back.node_tree.nodes
n_k.clear()
out_k = n_k.new("ShaderNodeOutputMaterial")
bsdf_k = n_k.new("ShaderNodeBsdfPrincipled")
tex_k_img = n_k.new("ShaderNodeTexImage")
tex_k_img.image = bpy.data.images.load(BACK_TEX)
tex_k_img.extension = 'CLIP'
uv_k_node = n_k.new("ShaderNodeUVMap")
uv_k_node.uv_map = "UV_Back"
bsdf_k.inputs["Roughness"].default_value = 0.48
mat_back.node_tree.links.new(uv_k_node.outputs["UV"], tex_k_img.inputs["Vector"])
mat_back.node_tree.links.new(tex_k_img.outputs["Color"], bsdf_k.inputs["Base Color"])
mat_back.node_tree.links.new(bsdf_k.outputs["BSDF"], out_k.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat_body)
ob.data.materials.append(mat_front)
ob.data.materials.append(mat_back)

for poly in ob.data.polygons:
    p_verts = [ob.matrix_world @ ob.data.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    norm = poly.normal
    
    if 0.02 < avg_z < 0.38 and abs(avg_x) < 0.20:
        if norm.y < -0.25:
            poly.material_index = 1
        elif norm.y > 0.25:
            poly.material_index = 2
        else:
            poly.material_index = 0
    else:
        poly.material_index = 0

for c in [cam_f, cam_b]:
    bpy.data.objects.remove(c, do_unlink=True)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)
print("SUCCESS_CLEAN_METIS_GLB_EXPORTED!")
