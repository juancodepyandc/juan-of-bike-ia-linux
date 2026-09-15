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
ortho_s = 0.54

cam_f = bpy.data.objects.new("CamProjF", bpy.data.cameras.new("CamProjF"))
cam_f.data.type = 'ORTHO'
cam_f.data.ortho_scale = ortho_s
cam_f.location = Vector((center.x, center.y - 2.0, torso_z))
cam_f.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_f)

cam_b = bpy.data.objects.new("CamProjB", bpy.data.cameras.new("CamProjB"))
cam_b.data.type = 'ORTHO'
cam_b.data.ortho_scale = ortho_s
cam_b.location = Vector((center.x, center.y + 2.0, torso_z))
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

# Build Material
mat = bpy.data.materials.new(name="MasterShader")
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()

out_n = nodes.new("ShaderNodeOutputMaterial")
emit_n = nodes.new("ShaderNodeEmission")

tex_base = nodes.new("ShaderNodeTexImage")
tex_base.image = bpy.data.images.load(BASE_TEX)
uv_base_node = nodes.new("ShaderNodeUVMap")
uv_base_node.uv_map = uv_main
mat.node_tree.links.new(uv_base_node.outputs["UV"], tex_base.inputs["Vector"])

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

geom = nodes.new("ShaderNodeNewGeometry")
sep_p = nodes.new("ShaderNodeSeparateXYZ")
mat.node_tree.links.new(geom.outputs["Position"], sep_p.inputs["Vector"])

z_min = nodes.new("ShaderNodeMath")
z_min.operation = 'GREATER_THAN'
z_min.inputs[1].default_value = -0.18
mat.node_tree.links.new(sep_p.outputs["Z"], z_min.inputs[0])

z_max = nodes.new("ShaderNodeMath")
z_max.operation = 'LESS_THAN'
z_max.inputs[1].default_value = 0.42
mat.node_tree.links.new(sep_p.outputs["Z"], z_max.inputs[0])

z_gate = nodes.new("ShaderNodeMath")
z_gate.operation = 'MULTIPLY'
mat.node_tree.links.new(z_min.outputs["Value"], z_gate.inputs[0])
mat.node_tree.links.new(z_max.outputs["Value"], z_gate.inputs[1])

x_abs = nodes.new("ShaderNodeMath")
x_abs.operation = 'ABSOLUTE'
mat.node_tree.links.new(sep_p.outputs["X"], x_abs.inputs[0])

x_max = nodes.new("ShaderNodeMath")
x_max.operation = 'LESS_THAN'
x_max.inputs[1].default_value = 0.32
mat.node_tree.links.new(x_abs.outputs["Value"], x_max.inputs[0])

box_gate = nodes.new("ShaderNodeMath")
box_gate.operation = 'MULTIPLY'
mat.node_tree.links.new(z_gate.outputs["Value"], box_gate.inputs[0])
mat.node_tree.links.new(x_max.outputs["Value"], box_gate.inputs[1])

y_f = nodes.new("ShaderNodeMath")
y_f.operation = 'LESS_THAN'
y_f.inputs[1].default_value = 0.00
mat.node_tree.links.new(sep_p.outputs["Y"], y_f.inputs[0])

m_front = nodes.new("ShaderNodeMath")
m_front.operation = 'MULTIPLY'
mat.node_tree.links.new(box_gate.outputs["Value"], m_front.inputs[0])
mat.node_tree.links.new(y_f.outputs["Value"], m_front.inputs[1])

y_b = nodes.new("ShaderNodeMath")
y_b.operation = 'GREATER_THAN'
y_b.inputs[1].default_value = 0.00
mat.node_tree.links.new(sep_p.outputs["Y"], y_b.inputs[0])

m_back = nodes.new("ShaderNodeMath")
m_back.operation = 'MULTIPLY'
mat.node_tree.links.new(box_gate.outputs["Value"], m_back.inputs[0])
mat.node_tree.links.new(y_b.outputs["Value"], m_back.inputs[1])

# Mix
mix1 = nodes.new("ShaderNodeMixRGB")
mat.node_tree.links.new(m_front.outputs["Value"], mix1.inputs["Fac"])
mat.node_tree.links.new(tex_base.outputs["Color"], mix1.inputs["Color1"])
mat.node_tree.links.new(tex_f.outputs["Color"], mix1.inputs["Color2"])

mix2 = nodes.new("ShaderNodeMixRGB")
mat.node_tree.links.new(m_back.outputs["Value"], mix2.inputs["Fac"])
mat.node_tree.links.new(mix1.outputs["Color"], mix2.inputs["Color1"])
mat.node_tree.links.new(tex_b.outputs["Color"], mix2.inputs["Color2"])

mat.node_tree.links.new(mix2.outputs["Color"], emit_n.inputs["Color"])
mat.node_tree.links.new(emit_n.outputs["Emission"], out_n.inputs["Surface"])

final_tex = bpy.data.images.new("MasterBakeFlawless4K", 4096, 4096)
target_n = nodes.new("ShaderNodeTexImage")
target_n.image = final_tex
nodes.active = target_n

ob.active_material = mat

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.margin = 8

print("Baking 4K Master Texture...")
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
print("SUCCESS_FLAWLESS_MASTER_GLB!")
