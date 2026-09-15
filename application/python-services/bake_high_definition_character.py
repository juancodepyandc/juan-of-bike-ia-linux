import bpy
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
ENHANCED_BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
FRONT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
BACK_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
OUTPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
ob = bpy.context.active_object
bpy.ops.object.shade_smooth()

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

base_img = bpy.data.images.load(ENHANCED_BASE_TEX)

baked_tshirt_f = bpy.data.images.new("BakedTshirtF", width=4096, height=4096, alpha=True)
baked_tshirt_f_mask = bpy.data.images.new("BakedTshirtFMask", width=4096, height=4096, alpha=False)
baked_tshirt_b = bpy.data.images.new("BakedTshirtB", width=4096, height=4096, alpha=True)
baked_tshirt_b_mask = bpy.data.images.new("BakedTshirtBMask", width=4096, height=4096, alpha=False)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "GPU"
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = "EMIT"

torso_z = center.z + size.z * 0.08
ortho_scale_tshirt = 0.54

# True Orthographic Projection Cameras
cam_tf_data = bpy.data.cameras.new("CamTF")
cam_tf_data.type = 'ORTHO'
cam_tf_data.ortho_scale = ortho_scale_tshirt
cam_tf = bpy.data.objects.new("CamTF", cam_tf_data)
cam_tf.location = Vector((center.x, center.y - 3.0, torso_z))
cam_tf.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
bpy.context.scene.collection.objects.link(cam_tf)

cam_tb_data = bpy.data.cameras.new("CamTB")
cam_tb_data.type = 'ORTHO'
cam_tb_data.ortho_scale = ortho_scale_tshirt
cam_tb = bpy.data.objects.new("CamTB", cam_tb_data)
cam_tb.location = Vector((center.x, center.y + 3.0, torso_z))
cam_tb.rotation_euler = (math.pi / 2.0, 0.0, math.pi)
bpy.context.scene.collection.objects.link(cam_tb)

def bake_projection(cam_obj, tex_path, out_color_img, ortho_s):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    
    mat = bpy.data.materials.new(name="BakeColor")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_emit = nodes.new("ShaderNodeEmission")
    n_img = nodes.new("ShaderNodeTexImage")
    n_img.image = bpy.data.images.load(tex_path)
    n_img.extension = 'CLIP'
    
    n_tc = nodes.new("ShaderNodeTexCoord")
    n_tc.object = cam_obj
    
    n_map = nodes.new("ShaderNodeMapping")
    n_map.vector_type = "POINT"
    n_map.inputs["Location"].default_value = (0.5, 0.5, 0.0)
    n_map.inputs["Scale"].default_value = (1.0 / ortho_s, 1.0 / ortho_s, 1.0)
    
    mat.node_tree.links.new(n_tc.outputs["Object"], n_map.inputs["Vector"])
    mat.node_tree.links.new(n_map.outputs["Vector"], n_img.inputs["Vector"])
    mat.node_tree.links.new(n_img.outputs["Color"], n_emit.inputs["Color"])
    mat.node_tree.links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
    
    n_target = nodes.new("ShaderNodeTexImage")
    n_target.image = out_color_img
    nodes.active = n_target
    
    ob.active_material = mat
    print(f"Baking Color for {cam_obj.name}...")
    bpy.ops.object.bake(type="EMIT")

def bake_mask(cam_obj, out_mask_img, is_front=True):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    
    mat_m = bpy.data.materials.new(name="BakeMask")
    mat_m.use_nodes = True
    nodes_m = mat_m.node_tree.nodes
    nodes_m.clear()
    
    m_out = nodes_m.new("ShaderNodeOutputMaterial")
    m_emit = nodes_m.new("ShaderNodeEmission")
    
    m_geom = nodes_m.new("ShaderNodeNewGeometry")
    m_sep_p = nodes_m.new("ShaderNodeSeparateXYZ")
    mat_m.node_tree.links.new(m_geom.outputs["Position"], m_sep_p.inputs["Vector"])
    
    m_y_check = nodes_m.new("ShaderNodeMath")
    if is_front:
        m_y_check.operation = "LESS_THAN"
        m_y_check.inputs[1].default_value = 0.05
        mat_m.node_tree.links.new(m_sep_p.outputs["Y"], m_y_check.inputs[0])
    else:
        m_y_check.operation = "GREATER_THAN"
        m_y_check.inputs[1].default_value = -0.05
        mat_m.node_tree.links.new(m_sep_p.outputs["Y"], m_y_check.inputs[0])
        
    m_z_min = nodes_m.new("ShaderNodeMath")
    m_z_min.operation = "GREATER_THAN"
    m_z_min.inputs[1].default_value = -0.18
    mat_m.node_tree.links.new(m_sep_p.outputs["Z"], m_z_min.inputs[0])
    
    m_z_max = nodes_m.new("ShaderNodeMath")
    m_z_max.operation = "LESS_THAN"
    m_z_max.inputs[1].default_value = 0.42
    mat_m.node_tree.links.new(m_sep_p.outputs["Z"], m_z_max.inputs[0])
    
    m_mult1 = nodes_m.new("ShaderNodeMath")
    m_mult1.operation = "MULTIPLY"
    mat_m.node_tree.links.new(m_y_check.outputs["Value"], m_mult1.inputs[0])
    mat_m.node_tree.links.new(m_z_min.outputs["Value"], m_mult1.inputs[1])
    
    m_mult2 = nodes_m.new("ShaderNodeMath")
    m_mult2.operation = "MULTIPLY"
    mat_m.node_tree.links.new(m_mult1.outputs["Value"], m_mult2.inputs[0])
    mat_m.node_tree.links.new(m_z_max.outputs["Value"], m_mult2.inputs[1])
    
    m_x_abs = nodes_m.new("ShaderNodeMath")
    m_x_abs.operation = "ABSOLUTE"
    mat_m.node_tree.links.new(m_sep_p.outputs["X"], m_x_abs.inputs[0])
    
    m_x_max = nodes_m.new("ShaderNodeMath")
    m_x_max.operation = "LESS_THAN"
    m_x_max.inputs[1].default_value = 0.32
    mat_m.node_tree.links.new(m_x_abs.outputs["Value"], m_x_max.inputs[0])
    
    m_mult3 = nodes_m.new("ShaderNodeMath")
    m_mult3.operation = "MULTIPLY"
    mat_m.node_tree.links.new(m_mult2.outputs["Value"], m_mult3.inputs[0])
    mat_m.node_tree.links.new(m_x_max.outputs["Value"], m_mult3.inputs[1])
    
    mat_m.node_tree.links.new(m_mult3.outputs["Value"], m_emit.inputs["Color"])
    mat_m.node_tree.links.new(m_emit.outputs["Emission"], m_out.inputs["Surface"])
    
    m_target = nodes_m.new("ShaderNodeTexImage")
    m_target.image = out_mask_img
    nodes_m.active = m_target
    
    ob.active_material = mat_m
    print(f"Baking Mask for {cam_obj.name}...")
    bpy.ops.object.bake(type="EMIT")

# Bake T-shirt front
bake_projection(cam_tf, FRONT_TEX, baked_tshirt_f, ortho_scale_tshirt)
bake_mask(cam_tf, baked_tshirt_f_mask, is_front=True)

# Bake T-shirt back
bake_projection(cam_tb, BACK_TEX, baked_tshirt_b, ortho_scale_tshirt)
bake_mask(cam_tb, baked_tshirt_b_mask, is_front=False)

# Composite Pixels
base_pixels = list(base_img.pixels)
tf_pixels = list(baked_tshirt_f.pixels)
tf_m = list(baked_tshirt_f_mask.pixels)

tb_pixels = list(baked_tshirt_b.pixels)
tb_m = list(baked_tshirt_b_mask.pixels)

num_pixels = len(base_pixels) // 4
for i in range(num_pixels):
    idx = i * 4
    mtf = tf_m[idx]
    mtb = tb_m[idx]
    
    if mtf > 0.01:
        base_pixels[idx]     = tf_pixels[idx]
        base_pixels[idx + 1] = tf_pixels[idx + 1]
        base_pixels[idx + 2] = tf_pixels[idx + 2]
    elif mtb > 0.01:
        base_pixels[idx]     = tb_pixels[idx]
        base_pixels[idx + 1] = tb_pixels[idx + 1]
        base_pixels[idx + 2] = tb_pixels[idx + 2]

final_master_img = bpy.data.images.new("MasterCompositeTex4K", width=4096, height=4096)
final_master_img.pixels = base_pixels

# High Quality PBR Material
mat_final = bpy.data.materials.new(name="MasterPBRMaterial")
mat_final.use_nodes = True
nodes_f = mat_final.node_tree.nodes
nodes_f.clear()

out_f = nodes_f.new("ShaderNodeOutputMaterial")
bsdf_f = nodes_f.new("ShaderNodeBsdfPrincipled")
tex_f = nodes_f.new("ShaderNodeTexImage")
tex_f.image = final_master_img

bsdf_f.inputs["Roughness"].default_value = 0.48
bsdf_f.inputs["Metallic"].default_value = 0.0

mat_final.node_tree.links.new(tex_f.outputs["Color"], bsdf_f.inputs["Base Color"])
mat_final.node_tree.links.new(bsdf_f.outputs["BSDF"], out_f.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat_final)

for c in [cam_tf, cam_tb]:
    bpy.data.objects.remove(c, do_unlink=True)

bpy.ops.export_scene.gltf(
    filepath=OUTPUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)

print(f"\nSUCCESS_EXPORTED_HD_MASTER_GLB: {OUTPUT_GLB}\n")
