import bpy, math, os, sys
import numpy as np
from mathutils import Vector

in_glb = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_trellis_raw.glb"
front_photo_path = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_master_front.png"
back_photo_path = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_master_back.png"
out_glb = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_ultra4k.glb"
tex_res = 4096

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=in_glb)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise RuntimeError("No mesh in GLB")
ob = max(meshes, key=lambda o: len(o.data.polygons))
me = ob.data
mw = ob.matrix_world

# Bounds & centering
verts = [mw @ v.co for v in me.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

# Smart project UV if needed or ensure UV exists
if not me.uv_layers:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

uv_native = me.uv_layers[0].name

# Setup Front Camera
scale = size[2] * 1.02
cam_front_data = bpy.data.cameras.new("cam_front")
cam_front_data.type = "ORTHO"
cam_front_data.ortho_scale = scale
cam_front = bpy.data.objects.new("cam_front", cam_front_data)
bpy.context.scene.collection.objects.link(cam_front)
dist = size[1] * 4.0
cam_front.location = Vector((center[0], center[1] - dist, center[2] + size[2] * 0.015))
cam_front.rotation_euler = (math.pi / 2.0, 0.0, 0.0)

# Setup Back Camera
cam_back_data = bpy.data.cameras.new("cam_back")
cam_back_data.type = "ORTHO"
cam_back_data.ortho_scale = scale
cam_back = bpy.data.objects.new("cam_back", cam_back_data)
bpy.context.scene.collection.objects.link(cam_back)
cam_back.location = Vector((center[0], center[1] + dist, center[2] + size[2] * 0.015))
cam_back.rotation_euler = (math.pi / 2.0, 0.0, math.pi)

bpy.context.view_layer.update()

# 1. Front UV project
uv_front = me.uv_layers.new(name="UV_Front_Project")
M_front = cam_front.matrix_world.inverted()
for poly in me.polygons:
    for loop_idx in poly.loop_indices:
        v_idx = me.loops[loop_idx].vertex_index
        p_world = mw @ me.vertices[v_idx].co
        p_cam = M_front @ p_world
        u = (p_cam.x / scale) + 0.5
        v = (p_cam.y / scale) + 0.5
        uv_front.data[loop_idx].uv = (u, v)

# 2. Back UV project
uv_back = me.uv_layers.new(name="UV_Back_Project")
M_back = cam_back.matrix_world.inverted()
for poly in me.polygons:
    for loop_idx in poly.loop_indices:
        v_idx = me.loops[loop_idx].vertex_index
        p_world = mw @ me.vertices[v_idx].co
        p_cam = M_back @ p_world
        u = (p_cam.x / scale) + 0.5
        v = (p_cam.y / scale) + 0.5
        uv_back.data[loop_idx].uv = (u, v)

me.uv_layers.active = me.uv_layers[uv_native]

# Load Photos
img_front = bpy.data.images.load(front_photo_path, check_existing=False)
img_back = bpy.data.images.load(back_photo_path, check_existing=False)

# Target Bake Atlas
img_front_bake = bpy.data.images.new("Bake_Front", tex_res, tex_res, alpha=True)
img_back_bake = bpy.data.images.new("Bake_Back", tex_res, tex_res, alpha=True)

# Shader setup for Front Bake
mat_bake = bpy.data.materials.new("Mat_Bake_Dual")
mat_bake.use_nodes = True
nt = mat_bake.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)

out = nt.nodes.new("ShaderNodeOutputMaterial")
emi = nt.nodes.new("ShaderNodeEmission")
nt.links.new(out.inputs["Surface"], emi.outputs["Emission"])

t_front = nt.nodes.new("ShaderNodeTexImage")
t_front.image = img_front
t_front.extension = "CLIP"

uv_map_f = nt.nodes.new("ShaderNodeUVMap")
uv_map_f.uv_map = "UV_Front_Project"
nt.links.new(t_front.inputs["Vector"], uv_map_f.outputs["UV"])
nt.links.new(emi.inputs["Color"], t_front.outputs["Color"])

target_node = nt.nodes.new("ShaderNodeTexImage")
target_node.image = img_front_bake
nt.nodes.active = target_node

ob.data.materials.clear()
ob.data.materials.append(mat_bake)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "GPU"
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.bake.margin = 8
bpy.context.scene.render.bake.use_clear = True

bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob

print("Baking Front Photo...")
bpy.ops.object.bake(type="EMIT")

# Bake Back
nt.links.new(t_front.inputs["Vector"], nt.nodes.new("ShaderNodeUVMap").outputs["UV"])
t_back = nt.nodes.new("ShaderNodeTexImage")
t_back.image = img_back
t_back.extension = "CLIP"
uv_map_b = nt.nodes.new("ShaderNodeUVMap")
uv_map_b.uv_map = "UV_Back_Project"
nt.links.new(t_back.inputs["Vector"], uv_map_b.outputs["UV"])
nt.links.new(emi.inputs["Color"], t_back.outputs["Color"])

target_node.image = img_back_bake
print("Baking Back Photo...")
bpy.ops.object.bake(type="EMIT")

# Combine Front and Back
buf_front = np.empty(tex_res * tex_res * 4, dtype=np.float32)
img_front_bake.pixels.foreach_get(buf_front)
buf_front = buf_front.reshape(tex_res, tex_res, 4)

buf_back = np.empty(tex_res * tex_res * 4, dtype=np.float32)
img_back_bake.pixels.foreach_get(buf_back)
buf_back = buf_back.reshape(tex_res, tex_res, 4)

# Create final combined atlas
buf_combined = np.zeros((tex_res, tex_res, 4), dtype=np.float32)
buf_combined[:, :, 3] = 1.0

# Mask calculation based on luminance / non-black
front_mask = (buf_front[:, :, :3].sum(axis=2) > 0.02)[:, :, None]
back_mask = (buf_back[:, :, :3].sum(axis=2) > 0.02)[:, :, None]

# Front has priority on front, back on back
buf_combined[:, :, :3] = np.where(back_mask, buf_back[:, :, :3], buf_combined[:, :, :3])
buf_combined[:, :, :3] = np.where(front_mask, buf_front[:, :, :3], buf_combined[:, :, :3])

img_final = bpy.data.images.new("Atlas_Final_4K", tex_res, tex_res, alpha=False)
img_final.pixels.foreach_set(buf_combined.ravel())
img_final.pack()

# Final PBR Material
mat_final = bpy.data.materials.new("Mat_Final_PBR_4K")
mat_final.use_nodes = True
nt_f = mat_final.node_tree
for n in list(nt_f.nodes): nt_f.nodes.remove(n)

out_f = nt_f.nodes.new("ShaderNodeOutputMaterial")
bsdf_f = nt_f.nodes.new("ShaderNodeBsdfPrincipled")
nt_f.links.new(out_f.inputs["Surface"], bsdf_f.outputs["BSDF"])

tex_alb = nt_f.nodes.new("ShaderNodeTexImage")
tex_alb.image = img_final
nt_f.links.new(bsdf_f.inputs["Base Color"], tex_alb.outputs["Color"])

bsdf_f.inputs["Roughness"].default_value = 0.50

ob.data.materials.clear()
ob.data.materials.append(mat_final)

me.uv_layers.remove(uv_front)
me.uv_layers.remove(uv_back)

bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format="GLB",
    export_materials="EXPORT"
)
print("DUAL_BAKE_SUCCESS")
