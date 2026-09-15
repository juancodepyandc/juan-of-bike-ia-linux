import bpy
import os
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
FRONT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
BACK_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
OUTPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
ob = max(meshes, key=lambda o: len(o.data.polygons))

bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active = ob

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

print(f"Mesh: center={center}, size={size}")

orig_mat = ob.active_material
orig_img = None
if orig_mat and orig_mat.use_nodes:
    for n in orig_mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            orig_img = n.image
            break

ortho_scale = 0.52
torso_z = center.z + size.z * 0.08

# Front Camera
cam_f = bpy.data.objects.new("CamFront", bpy.data.cameras.new("CamFront"))
cam_f.location = Vector((center.x, center.y - 3.0, torso_z))
cam_f.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
bpy.context.scene.collection.objects.link(cam_f)

# Back Camera
cam_b = bpy.data.objects.new("CamBack", bpy.data.cameras.new("CamBack"))
cam_b.location = Vector((center.x, center.y + 3.0, torso_z))
cam_b.rotation_euler = (math.pi / 2.0, 0.0, math.pi)
bpy.context.scene.collection.objects.link(cam_b)

baked_front = bpy.data.images.new("BakedFront", width=4096, height=4096, alpha=True)
baked_front_mask = bpy.data.images.new("BakedFrontMask", width=4096, height=4096, alpha=False)
baked_back = bpy.data.images.new("BakedBack", width=4096, height=4096, alpha=True)
baked_back_mask = bpy.data.images.new("BakedBackMask", width=4096, height=4096, alpha=False)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "GPU"
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = "EMIT"

def bake_decal(cam_obj, tex_path, out_color_img, out_mask_img, is_front=True):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    
    # Color
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
    n_map.inputs["Scale"].default_value = (1.0 / ortho_scale, 1.0 / ortho_scale, 1.0)
    
    mat.node_tree.links.new(n_tc.outputs["Object"], n_map.inputs["Vector"])
    mat.node_tree.links.new(n_map.outputs["Vector"], n_img.inputs["Vector"])
    mat.node_tree.links.new(n_img.outputs["Color"], n_emit.inputs["Color"])
    mat.node_tree.links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
    
    n_target = nodes.new("ShaderNodeTexImage")
    n_target.image = out_color_img
    nodes.active = n_target
    
    ob.active_material = mat
    print(f"Baking {'Front' if is_front else 'Back'} Decal Color...")
    bpy.ops.object.bake(type="EMIT")
    
    # Mask
    mat_m = bpy.data.materials.new(name="BakeMask")
    mat_m.use_nodes = True
    nodes_m = mat_m.node_tree.nodes
    nodes_m.clear()
    
    m_out = nodes_m.new("ShaderNodeOutputMaterial")
    m_emit = nodes_m.new("ShaderNodeEmission")
    
    m_geom = nodes_m.new("ShaderNodeNewGeometry")
    m_sep_n = nodes_m.new("ShaderNodeSeparateXYZ")
    mat_m.node_tree.links.new(m_geom.outputs["Normal"], m_sep_n.inputs["Vector"])
    
    m_norm_check = nodes_m.new("ShaderNodeMath")
    if is_front:
        m_norm_check.operation = "LESS_THAN"
        m_norm_check.inputs[1].default_value = -0.30
        mat_m.node_tree.links.new(m_sep_n.outputs["Y"], m_norm_check.inputs[0])
    else:
        m_norm_check.operation = "GREATER_THAN"
        m_norm_check.inputs[1].default_value = 0.30
        mat_m.node_tree.links.new(m_sep_n.outputs["Y"], m_norm_check.inputs[0])
        
    m_sep_p = nodes_m.new("ShaderNodeSeparateXYZ")
    mat_m.node_tree.links.new(m_geom.outputs["Position"], m_sep_p.inputs["Vector"])
    
    m_z_min = nodes_m.new("ShaderNodeMath")
    m_z_min.operation = "GREATER_THAN"
    m_z_min.inputs[1].default_value = -0.15
    mat_m.node_tree.links.new(m_sep_p.outputs["Z"], m_z_min.inputs[0])
    
    m_z_max = nodes_m.new("ShaderNodeMath")
    m_z_max.operation = "LESS_THAN"
    m_z_max.inputs[1].default_value = 0.44
    mat_m.node_tree.links.new(m_sep_p.outputs["Z"], m_z_max.inputs[0])
    
    m_x_abs = nodes_m.new("ShaderNodeMath")
    m_x_abs.operation = "ABSOLUTE"
    mat_m.node_tree.links.new(m_sep_p.outputs["X"], m_x_abs.inputs[0])
    
    m_x_max = nodes_m.new("ShaderNodeMath")
    m_x_max.operation = "LESS_THAN"
    m_x_max.inputs[1].default_value = 0.32
    mat_m.node_tree.links.new(m_x_abs.outputs["Value"], m_x_max.inputs[0])
    
    m_mult1 = nodes_m.new("ShaderNodeMath")
    m_mult1.operation = "MULTIPLY"
    mat_m.node_tree.links.new(m_norm_check.outputs["Value"], m_mult1.inputs[0])
    mat_m.node_tree.links.new(m_z_min.outputs["Value"], m_mult1.inputs[1])
    
    m_mult2 = nodes_m.new("ShaderNodeMath")
    m_mult2.operation = "MULTIPLY"
    mat_m.node_tree.links.new(m_mult1.outputs["Value"], m_mult2.inputs[0])
    mat_m.node_tree.links.new(m_z_max.outputs["Value"], m_mult2.inputs[1])
    
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
    print(f"Baking {'Front' if is_front else 'Back'} Mask...")
    bpy.ops.object.bake(type="EMIT")

bake_decal(cam_f, FRONT_TEX, baked_front, baked_front_mask, is_front=True)
bake_decal(cam_b, BACK_TEX, baked_back, baked_back_mask, is_front=False)

orig_pixels = list(orig_img.pixels)
f_pixels = list(baked_front.pixels)
fm_pixels = list(baked_front_mask.pixels)
b_pixels = list(baked_back.pixels)
bm_pixels = list(baked_back_mask.pixels)

num_pixels = len(orig_pixels) // 4
for i in range(num_pixels):
    idx = i * 4
    mask_f = fm_pixels[idx]
    mask_b = bm_pixels[idx]
    
    if mask_f > 0.01:
        orig_pixels[idx]     = f_pixels[idx]
        orig_pixels[idx + 1] = f_pixels[idx + 1]
        orig_pixels[idx + 2] = f_pixels[idx + 2]
    elif mask_b > 0.01:
        orig_pixels[idx]     = b_pixels[idx]
        orig_pixels[idx + 1] = b_pixels[idx + 1]
        orig_pixels[idx + 2] = b_pixels[idx + 2]

final_baked_img = bpy.data.images.new("FinalMasterTex", width=4096, height=4096)
final_baked_img.pixels = orig_pixels

mat_final = bpy.data.materials.new(name="MasterFinalMaterial")
mat_final.use_nodes = True
nodes_f = mat_final.node_tree.nodes
nodes_f.clear()

out_f = nodes_f.new("ShaderNodeOutputMaterial")
bsdf_f = nodes_f.new("ShaderNodeBsdfPrincipled")
tex_f = nodes_f.new("ShaderNodeTexImage")
tex_f.image = final_baked_img

bsdf_f.inputs["Roughness"].default_value = 0.65
bsdf_f.inputs["Metallic"].default_value = 0.0

mat_final.node_tree.links.new(tex_f.outputs["Color"], bsdf_f.inputs["Base Color"])
mat_final.node_tree.links.new(bsdf_f.outputs["BSDF"], out_f.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat_final)

bpy.data.objects.remove(cam_f, do_unlink=True)
bpy.data.objects.remove(cam_b, do_unlink=True)

bpy.ops.export_scene.gltf(
    filepath=OUTPUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)

print(f"\nEXPORTED_SOLID_MASTER_GLB: {OUTPUT_GLB}\n")
