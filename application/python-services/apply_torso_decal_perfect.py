import bpy, math, os, sys
import numpy as np
from mathutils import Vector

in_glb = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_trellis_raw.glb"
patch_front = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/tshirt_front_aligned.png"
patch_back = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/tshirt_back_aligned.png"
out_glb = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"
tex_res = 4096

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=in_glb)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
me = ob.data
mw = ob.matrix_world

# Bounds
verts = [mw @ v.co for v in me.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

orig_mat = ob.data.materials[0] if ob.data.materials else None
orig_img = None
if orig_mat and orig_mat.use_nodes:
    for n in orig_mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            orig_img = n.image
            break

if orig_img:
    w, h = orig_img.size
    buf_base = np.empty(w * h * 4, dtype=np.float32)
    orig_img.pixels.foreach_get(buf_base)
    buf_base = buf_base.reshape(h, w, 4)
    if (w, h) != (tex_res, tex_res):
        import cv2
        buf_base = cv2.resize(buf_base, (tex_res, tex_res), interpolation=cv2.INTER_LANCZOS4)
else:
    buf_base = np.zeros((tex_res, tex_res, 4), dtype=np.float32)
    buf_base[:, :, 3] = 1.0

# Decal Cameras aligned to exact torso bounds: Z in [-0.05, 0.22]
torso_z_center = 0.085
torso_scale = 0.29

cam_f_data = bpy.data.cameras.new("cam_decal_front")
cam_f_data.type = "ORTHO"
cam_f_data.ortho_scale = torso_scale
cam_f = bpy.data.objects.new("cam_decal_front", cam_f_data)
bpy.context.scene.collection.objects.link(cam_f)
cam_f.location = Vector((center.x, center.y - 1.5, torso_z_center))
cam_f.rotation_euler = (math.pi / 2.0, 0.0, 0.0)

cam_b_data = bpy.data.cameras.new("cam_decal_back")
cam_b_data.type = "ORTHO"
cam_b_data.ortho_scale = torso_scale
cam_b = bpy.data.objects.new("cam_decal_back", cam_b_data)
bpy.context.scene.collection.objects.link(cam_b)
cam_b.location = Vector((center.x, center.y + 1.5, torso_z_center))
cam_b.rotation_euler = (math.pi / 2.0, 0.0, math.pi)

bpy.context.view_layer.update()

# Project UVs
uv_f = me.uv_layers.new(name="UV_Decal_Front")
M_f = cam_f.matrix_world.inverted()
scale_f = cam_f_data.ortho_scale
for poly in me.polygons:
    for loop_idx in poly.loop_indices:
        v_idx = me.loops[loop_idx].vertex_index
        p_world = mw @ me.vertices[v_idx].co
        p_cam = M_f @ p_world
        u = (p_cam.x / scale_f) + 0.5
        v = (p_cam.y / scale_f) + 0.5
        uv_f.data[loop_idx].uv = (u, v)

uv_b = me.uv_layers.new(name="UV_Decal_Back")
M_b = cam_b.matrix_world.inverted()
scale_b = cam_b_data.ortho_scale
for poly in me.polygons:
    for loop_idx in poly.loop_indices:
        v_idx = me.loops[loop_idx].vertex_index
        p_world = mw @ me.vertices[v_idx].co
        p_cam = M_b @ p_world
        u = (p_cam.x / scale_b) + 0.5
        v = (p_cam.y / scale_b) + 0.5
        uv_b.data[loop_idx].uv = (u, v)

uv_native = me.uv_layers[0].name
me.uv_layers.active = me.uv_layers[uv_native]

# Images
img_p_f = bpy.data.images.load(patch_front)
img_p_b = bpy.data.images.load(patch_back)

img_bake_f = bpy.data.images.new("Decal_Bake_Front", tex_res, tex_res, alpha=True)
img_bake_b = bpy.data.images.new("Decal_Bake_Back", tex_res, tex_res, alpha=True)

# Shader with Alpha + Normal Cull + Z Bound
mat_bake = bpy.data.materials.new("Mat_Bake_Torso")
mat_bake.use_nodes = True
nt = mat_bake.node_tree
nt.nodes.clear()

out = nt.nodes.new("ShaderNodeOutputMaterial")
emi = nt.nodes.new("ShaderNodeEmission")
nt.links.new(out.inputs["Surface"], emi.outputs["Emission"])

t_node = nt.nodes.new("ShaderNodeTexImage")
t_node.image = img_p_f
t_node.extension = "CLIP"

uv_map_n = nt.nodes.new("ShaderNodeUVMap")
uv_map_n.uv_map = "UV_Decal_Front"
nt.links.new(t_node.inputs["Vector"], uv_map_n.outputs["UV"])

geo_n = nt.nodes.new("ShaderNodeNewGeometry")
dot_n = nt.nodes.new("ShaderNodeVectorMath")
dot_n.operation = "DOT_PRODUCT"
dot_n.inputs[1].default_value = (0.0, -1.0, 0.0) # front
nt.links.new(geo_n.outputs["Normal"], dot_n.inputs[0])

sep_xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(geo_n.outputs["Position"], sep_xyz.inputs[0])

cmp_norm = nt.nodes.new("ShaderNodeMath")
cmp_norm.operation = "GREATER_THAN"
cmp_norm.inputs[1].default_value = 0.20
nt.links.new(dot_n.outputs["Value"], cmp_norm.inputs[0])

cmp_z_min = nt.nodes.new("ShaderNodeMath")
cmp_z_min.operation = "GREATER_THAN"
cmp_z_min.inputs[1].default_value = -0.05
nt.links.new(sep_xyz.outputs["Z"], cmp_z_min.inputs[0])

cmp_z_max = nt.nodes.new("ShaderNodeMath")
cmp_z_max.operation = "LESS_THAN"
cmp_z_max.inputs[1].default_value = 0.22
nt.links.new(sep_xyz.outputs["Z"], cmp_z_max.inputs[0])

mul_mask1 = nt.nodes.new("ShaderNodeMath")
mul_mask1.operation = "MULTIPLY"
nt.links.new(cmp_norm.outputs["Value"], mul_mask1.inputs[0])
nt.links.new(cmp_z_min.outputs["Value"], mul_mask1.inputs[1])

mul_mask2 = nt.nodes.new("ShaderNodeMath")
mul_mask2.operation = "MULTIPLY"
nt.links.new(mul_mask1.outputs["Value"], mul_mask2.inputs[0])
nt.links.new(cmp_z_max.outputs["Value"], mul_mask2.inputs[1])

mul_alpha = nt.nodes.new("ShaderNodeMath")
mul_alpha.operation = "MULTIPLY"
nt.links.new(mul_mask2.outputs["Value"], mul_alpha.inputs[0])
nt.links.new(t_node.outputs["Alpha"], mul_alpha.inputs[1])

mul_col = nt.nodes.new("ShaderNodeVectorMath")
mul_col.operation = "MULTIPLY"
nt.links.new(t_node.outputs["Color"], mul_col.inputs[0])
nt.links.new(mul_alpha.outputs["Value"], mul_col.inputs[1])

nt.links.new(emi.inputs["Color"], mul_col.outputs["Vector"])

target_n = nt.nodes.new("ShaderNodeTexImage")
target_n.image = img_bake_f
nt.nodes.active = target_n

ob.data.materials.clear()
ob.data.materials.append(mat_bake)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "GPU"
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.bake.margin = 4

bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob

print("Baking Front Aligned Decal...")
bpy.ops.object.bake(type="EMIT")

# Switch to Back Decal
t_node.image = img_p_b
uv_map_n.uv_map = "UV_Decal_Back"
dot_n.inputs[1].default_value = (0.0, 1.0, 0.0) # back
target_n.image = img_bake_b

print("Baking Back Aligned Decal...")
bpy.ops.object.bake(type="EMIT")

# Combine in Python
buf_f = np.empty(tex_res * tex_res * 4, dtype=np.float32)
img_bake_f.pixels.foreach_get(buf_f)
buf_f = buf_f.reshape(tex_res, tex_res, 4)

buf_b = np.empty(tex_res * tex_res * 4, dtype=np.float32)
img_bake_b.pixels.foreach_get(buf_b)
buf_b = buf_b.reshape(tex_res, tex_res, 4)

f_mask = (buf_f[:, :, :3].sum(axis=2) > 0.03)[:, :, None]
b_mask = (buf_b[:, :, :3].sum(axis=2) > 0.03)[:, :, None]

buf_final = buf_base.copy()
buf_final[:, :, :3] = np.where(b_mask, buf_b[:, :, :3], buf_final[:, :, :3])
buf_final[:, :, :3] = np.where(f_mask, buf_f[:, :, :3], buf_final[:, :, :3])

img_final = bpy.data.images.new("Atlas_Master_Aligned", tex_res, tex_res, alpha=False)
img_final.pixels.foreach_set(buf_final.ravel())
img_final.pack()

# Final PBR Material
mat_final = bpy.data.materials.new("Mat_Final_PBR")
mat_final.use_nodes = True
nt_f = mat_final.node_tree
nt_f.nodes.clear()

out_f = nt_f.nodes.new("ShaderNodeOutputMaterial")
bsdf_f = nt_f.nodes.new("ShaderNodeBsdfPrincipled")
nt_f.links.new(out_f.inputs["Surface"], bsdf_f.outputs["BSDF"])

tex_alb = nt_f.nodes.new("ShaderNodeTexImage")
tex_alb.image = img_final
nt_f.links.new(bsdf_f.inputs["Base Color"], tex_alb.outputs["Color"])

bsdf_f.inputs["Roughness"].default_value = 0.50

ob.data.materials.clear()
ob.data.materials.append(mat_final)

me.uv_layers.remove(uv_f)
me.uv_layers.remove(uv_b)

bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format="GLB",
    export_materials="EXPORT"
)
print(f"EXPORTED_PERFECT_ALIGNED_GLB: {out_glb}")
