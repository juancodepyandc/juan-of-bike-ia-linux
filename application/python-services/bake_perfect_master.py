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
bpy.ops.object.shade_smooth()

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

torso_z = center.z + size.z * 0.08
ortho_s = 0.54

# Setup True Projection Empties
empty_f = bpy.data.objects.new("EmptyF", None)
empty_f.location = Vector((center.x, center.y, torso_z))
empty_f.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
bpy.context.scene.collection.objects.link(empty_f)

empty_b = bpy.data.objects.new("EmptyB", None)
empty_b.location = Vector((center.x, center.y, torso_z))
empty_b.rotation_euler = (math.pi / 2.0, 0.0, math.pi)
bpy.context.scene.collection.objects.link(empty_b)

# Build Master Multi-Layer Shader Node Tree
mat = bpy.data.materials.new(name="MasterShader")
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.clear()

out_node = nodes.new("ShaderNodeOutputMaterial")
emit_node = nodes.new("ShaderNodeEmission")

# 1. Base Texture
base_img_node = nodes.new("ShaderNodeTexImage")
base_img_node.image = bpy.data.images.load(BASE_TEX)

# 2. Front T-Shirt Texture
tex_f = nodes.new("ShaderNodeTexImage")
tex_f.image = bpy.data.images.load(FRONT_TEX)
tex_f.extension = 'CLIP'

tc_f = nodes.new("ShaderNodeTexCoord")
tc_f.object = empty_f

map_f = nodes.new("ShaderNodeMapping")
map_f.vector_type = 'POINT'
map_f.inputs["Location"].default_value = (0.5, 0.5, 0.0)
map_f.inputs["Scale"].default_value = (1.0 / ortho_s, 1.0 / ortho_s, 1.0)
mat.node_tree.links.new(tc_f.outputs["Object"], map_f.inputs["Vector"])
mat.node_tree.links.new(map_f.outputs["Vector"], tex_f.inputs["Vector"])

# 3. Back T-Shirt Texture
tex_b = nodes.new("ShaderNodeTexImage")
tex_b.image = bpy.data.images.load(BACK_TEX)
tex_b.extension = 'CLIP'

tc_b = nodes.new("ShaderNodeTexCoord")
tc_b.object = empty_b

map_b = nodes.new("ShaderNodeMapping")
map_b.vector_type = 'POINT'
map_b.inputs["Location"].default_value = (0.5, 0.5, 0.0)
map_b.inputs["Scale"].default_value = (1.0 / ortho_s, 1.0 / ortho_s, 1.0)
mat.node_tree.links.new(tc_b.outputs["Object"], map_b.inputs["Vector"])
mat.node_tree.links.new(map_b.outputs["Vector"], tex_b.inputs["Vector"])

# 4. Spatial Position Masks
geom = nodes.new("ShaderNodeNewGeometry")
sep_p = nodes.new("ShaderNodeSeparateXYZ")
mat.node_tree.links.new(geom.outputs["Position"], sep_p.inputs["Vector"])

# Z limits (-0.18 < Z < 0.42)
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

# X limits (abs(X) < 0.32)
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

# Front mask (Y < 0.03)
y_front = nodes.new("ShaderNodeMath")
y_front.operation = 'LESS_THAN'
y_front.inputs[1].default_value = 0.03
mat.node_tree.links.new(sep_p.outputs["Y"], y_front.inputs[0])

front_mask = nodes.new("ShaderNodeMath")
front_mask.operation = 'MULTIPLY'
mat.node_tree.links.new(box_gate.outputs["Value"], front_mask.inputs[0])
mat.node_tree.links.new(y_front.outputs["Value"], front_mask.inputs[1])

# Back mask (Y > -0.03)
y_back = nodes.new("ShaderNodeMath")
y_back.operation = 'GREATER_THAN'
y_back.inputs[1].default_value = -0.03
mat.node_tree.links.new(sep_p.outputs["Y"], y_back.inputs[0])

back_mask = nodes.new("ShaderNodeMath")
back_mask.operation = 'MULTIPLY'
mat.node_tree.links.new(box_gate.outputs["Value"], back_mask.inputs[0])
mat.node_tree.links.new(y_back.outputs["Value"], back_mask.inputs[1])

# Mix Layers: Base -> Front -> Back
mix1 = nodes.new("ShaderNodeMixRGB")
mat.node_tree.links.new(front_mask.outputs["Value"], mix1.inputs["Fac"])
mat.node_tree.links.new(base_img_node.outputs["Color"], mix1.inputs["Color1"])
mat.node_tree.links.new(tex_f.outputs["Color"], mix1.inputs["Color2"])

mix2 = nodes.new("ShaderNodeMixRGB")
mat.node_tree.links.new(back_mask.outputs["Value"], mix2.inputs["Fac"])
mat.node_tree.links.new(mix1.outputs["Color"], mix2.inputs["Color1"])
mat.node_tree.links.new(tex_b.outputs["Color"], mix2.inputs["Color2"])

mat.node_tree.links.new(mix2.outputs["Color"], emit_node.inputs["Color"])
mat.node_tree.links.new(emit_node.outputs["Emission"], out_node.inputs["Surface"])

# Target 4K Bake Texture
final_bake_tex = bpy.data.images.new("FinalMasterBake4K", width=4096, height=4096)
target_tex_node = nodes.new("ShaderNodeTexImage")
target_tex_node.image = final_bake_tex
nodes.active = target_tex_node

ob.active_material = mat

# Bake with Cycles 16 samples for Anti-Aliased Quality
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.margin = 16

print("Baking 4K Master PBR Texture with 16 samples anti-aliased...")
bpy.ops.object.bake(type='EMIT')

# Create Final Clean PBR Material with baked texture
mat_pbr = bpy.data.materials.new(name="MasterPBRMaterial")
mat_pbr.use_nodes = True
nodes_p = mat_pbr.node_tree.nodes
nodes_p.clear()

out_p = nodes_p.new("ShaderNodeOutputMaterial")
bsdf_p = nodes_p.new("ShaderNodeBsdfPrincipled")
tex_p = nodes_p.new("ShaderNodeTexImage")
tex_p.image = final_bake_tex

bsdf_p.inputs["Roughness"].default_value = 0.48
bsdf_p.inputs["Metallic"].default_value = 0.0

mat_pbr.node_tree.links.new(tex_p.outputs["Color"], bsdf_p.inputs["Base Color"])
mat_pbr.node_tree.links.new(bsdf_p.outputs["BSDF"], out_p.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat_pbr)

for e in [empty_f, empty_b]:
    bpy.data.objects.remove(e, do_unlink=True)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)

print(f"\nSUCCESS_EXPORTED_PERFECT_MASTER_GLB: {OUT_GLB}\n")
