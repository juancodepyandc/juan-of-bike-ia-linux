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
ortho_s = 0.44  # Tighter framing for front chest

# 1. Planar UV Map for Front Decal
cam_f = bpy.data.objects.new("CamDecalF", bpy.data.cameras.new("CamDecalF"))
cam_f.data.type = 'ORTHO'
cam_f.data.ortho_scale = ortho_s
cam_f.location = Vector((center.x, center.y - 2.0, torso_z + 0.02))
cam_f.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_f)

cam_b = bpy.data.objects.new("CamDecalB", bpy.data.cameras.new("CamDecalB"))
cam_b.data.type = 'ORTHO'
cam_b.data.ortho_scale = ortho_s
cam_b.location = Vector((center.x, center.y + 2.0, torso_z + 0.02))
cam_b.rotation_euler = (math.pi / 2.0, 0, math.pi)
bpy.context.scene.collection.objects.link(cam_b)

uv_main = ob.data.uv_layers.active.name
uv_front = ob.data.uv_layers.new(name="UV_Front")
uv_back = ob.data.uv_layers.new(name="UV_Back")

mod_f = ob.modifiers.new("UVProjF", 'UV_PROJECT')
mod_f.uv_layer = "UV_Front"
mod_f.projector_count = 1
mod_f.projectors[0].object = cam_f
bpy.ops.object.modifier_apply(modifier="UVProjF")

mod_b = ob.modifiers.new("UVProjB", 'UV_PROJECT')
mod_b.uv_layer = "UV_Back"
mod_b.projector_count = 1
mod_b.projectors[0].object = cam_b
bpy.ops.object.modifier_apply(modifier="UVProjB")

ob.data.uv_layers[uv_main].active = True
ob.data.uv_layers[uv_main].active_render = True

# 2. Shader with strict normal & bounding box for crystal clear print
mat = bpy.data.materials.new(name="MasterShader")
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()

out_n = nodes.new("ShaderNodeOutputMaterial")
emit_n = nodes.new("ShaderNodeEmission")

# Base Skin / Pants / Hair texture
tex_base = nodes.new("ShaderNodeTexImage")
tex_base.image = bpy.data.images.load(BASE_TEX)
uv_base_node = nodes.new("ShaderNodeUVMap")
uv_base_node.uv_map = uv_main
mat.node_tree.links.new(uv_base_node.outputs["UV"], tex_base.inputs["Vector"])

# Front & Back Decals
tex_f = nodes.new("ShaderNodeTexImage")
tex_f.image = bpy.data.images.load(FRONT_TEX)
tex_f.extension = 'CLIP'
uv_f_node = nodes.new("ShaderNodeUVMap")
uv_f_node.uv_map = "UV_Front"
mat.node_tree.links.new(uv_f_node.outputs["UV"], tex_f.inputs["Vector"])

tex_b = nodes.new("ShaderNodeTexImage")
tex_b.image = bpy.data.images.load(BACK_TEX)
tex_b.extension = 'CLIP'
uv_b_node = nodes.new("ShaderNodeUVMap")
uv_b_node.uv_map = "UV_Back"
mat.node_tree.links.new(uv_b_node.outputs["UV"], tex_b.inputs["Vector"])

# Solid Matte Black for T-Shirt base
tshirt_solid_black = nodes.new("ShaderNodeRGB")
tshirt_solid_black.outputs["Color"].default_value = (0.043, 0.043, 0.055, 1.0) # #0b0b0e in sRGB

# Geometry checks
geom = nodes.new("ShaderNodeNewGeometry")
sep_p = nodes.new("ShaderNodeSeparateXYZ")
sep_n = nodes.new("ShaderNodeSeparateXYZ")
mat.node_tree.links.new(geom.outputs["Position"], sep_p.inputs["Vector"])
mat.node_tree.links.new(geom.outputs["Normal"], sep_n.inputs["Vector"])

# Torso Bounding Box (-0.16 < Z < 0.40, abs(X) < 0.30)
z_min_t = nodes.new("ShaderNodeMath")
z_min_t.operation = 'GREATER_THAN'
z_min_t.inputs[1].default_value = -0.16
mat.node_tree.links.new(sep_p.outputs["Z"], z_min_t.inputs[0])

z_max_t = nodes.new("ShaderNodeMath")
z_max_t.operation = 'LESS_THAN'
z_max_t.inputs[1].default_value = 0.40
mat.node_tree.links.new(sep_p.outputs["Z"], z_max_t.inputs[0])

x_max_t = nodes.new("ShaderNodeMath")
x_max_t.operation = 'LESS_THAN'
x_max_t.inputs[1].default_value = 0.30
x_abs_t = nodes.new("ShaderNodeMath")
x_abs_t.operation = 'ABSOLUTE'
mat.node_tree.links.new(sep_p.outputs["X"], x_abs_t.inputs[0])
mat.node_tree.links.new(x_abs_t.outputs["Value"], x_max_t.inputs[0])

m1 = nodes.new("ShaderNodeMath")
m1.operation = 'MULTIPLY'
mat.node_tree.links.new(z_min_t.outputs["Value"], m1.inputs[0])
mat.node_tree.links.new(z_max_t.outputs["Value"], m1.inputs[1])

torso_mask = nodes.new("ShaderNodeMath")
torso_mask.operation = 'MULTIPLY'
mat.node_tree.links.new(m1.outputs["Value"], torso_mask.inputs[0])
mat.node_tree.links.new(x_max_t.outputs["Value"], torso_mask.inputs[1])

# Front Chest Graphic Box (-0.14 < Z < 0.38, abs(X) < 0.21, Normal.Y < -0.30)
norm_f = nodes.new("ShaderNodeMath")
norm_f.operation = 'LESS_THAN'
norm_f.inputs[1].default_value = -0.30
mat.node_tree.links.new(sep_n.outputs["Y"], norm_f.inputs[0])

front_print_mask = nodes.new("ShaderNodeMath")
front_print_mask.operation = 'MULTIPLY'
mat.node_tree.links.new(torso_mask.outputs["Value"], front_print_mask.inputs[0])
mat.node_tree.links.new(norm_f.outputs["Value"], front_print_mask.inputs[1])

# Back Print Mask (Normal.Y > 0.30)
norm_b = nodes.new("ShaderNodeMath")
norm_b.operation = 'GREATER_THAN'
norm_b.inputs[1].default_value = 0.30
mat.node_tree.links.new(sep_n.outputs["Y"], norm_b.inputs[0])

back_print_mask = nodes.new("ShaderNodeMath")
back_print_mask.operation = 'MULTIPLY'
mat.node_tree.links.new(torso_mask.outputs["Value"], back_print_mask.inputs[0])
mat.node_tree.links.new(norm_b.outputs["Value"], back_print_mask.inputs[1])

# Layering: Base Skin/Pants -> Solid Black T-Shirt -> Front Print -> Back Print
mix_tshirt = nodes.new("ShaderNodeMixRGB")
mat.node_tree.links.new(torso_mask.outputs["Value"], mix_tshirt.inputs["Fac"])
mat.node_tree.links.new(tex_base.outputs["Color"], mix_tshirt.inputs["Color1"])
mat.node_tree.links.new(tshirt_solid_black.outputs["Color"], mix_tshirt.inputs["Color2"])

mix_front = nodes.new("ShaderNodeMixRGB")
mat.node_tree.links.new(front_print_mask.outputs["Value"], mix_front.inputs["Fac"])
mat.node_tree.links.new(mix_tshirt.outputs["Color"], mix_front.inputs["Color1"])
mat.node_tree.links.new(tex_f.outputs["Color"], mix_front.inputs["Color2"])

mix_back = nodes.new("ShaderNodeMixRGB")
mat.node_tree.links.new(back_print_mask.outputs["Value"], mix_back.inputs["Fac"])
mat.node_tree.links.new(mix_front.outputs["Color"], mix_back.inputs["Color1"])
mat.node_tree.links.new(tex_b.outputs["Color"], mix_back.inputs["Color2"])

mat.node_tree.links.new(mix_back.outputs["Color"], emit_n.inputs["Color"])
mat.node_tree.links.new(emit_n.outputs["Emission"], out_n.inputs["Surface"])

final_tex = bpy.data.images.new("MasterBakeClean4K", 4096, 4096)
target_n = nodes.new("ShaderNodeTexImage")
target_n.image = final_tex
nodes.active = target_n

ob.active_material = mat

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.margin = 8

print("Baking 4K Master Texture with Clean Decal Pipeline...")
bpy.ops.object.bake(type='EMIT')

# PBR export
mat_pbr = bpy.data.materials.new(name="MasterPBR")
mat_pbr.use_nodes = True
nodes_p = mat_pbr.node_tree.nodes
nodes_p.clear()

out_p = nodes_p.new("ShaderNodeOutputMaterial")
bsdf_p = nodes_p.new("ShaderNodeBsdfPrincipled")
tex_p = nodes_p.new("ShaderNodeTexImage")
tex_p.image = final_tex
bsdf_p.inputs["Roughness"].default_value = 0.48
bsdf_p.inputs["Metallic"].default_value = 0.0

mat_pbr.node_tree.links.new(tex_p.outputs["Color"], bsdf_p.inputs["Base Color"])
mat_pbr.node_tree.links.new(bsdf_p.outputs["BSDF"], out_p.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat_pbr)

for uv_name in ["UV_Front", "UV_Back"]:
    ob.data.uv_layers.remove(ob.data.uv_layers[uv_name])

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
print("SUCCESS_CLEAN_DECAL_MASTER_GLB!")
