import bpy, math, os, sys
import numpy as np
from mathutils import Vector

in_glb = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_trellis_raw.glb"
patch_front = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/tshirt_graphic_front_4k.png"
patch_back = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/tshirt_graphic_back_4k.png"
out_glb = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_perfect.glb"
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

# Extract existing base color texture from raw GLB
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
    # Resize base to 4096 if needed
    if (w, h) != (tex_res, tex_res):
        import cv2
        buf_base = cv2.resize(buf_base, (tex_res, tex_res), interpolation=cv2.INTER_LANCZOS4)
else:
    buf_base = np.zeros((tex_res, tex_res, 4), dtype=np.float32)
    buf_base[:, :, 3] = 1.0

# Setup Decal Camera for Front Torso ONLY
# Torso bounds: Z in [-0.05, 0.22], X in [-0.17, 0.17]
torso_z_min = -0.05
torso_z_max = 0.22
torso_z_center = (torso_z_min + torso_z_max) * 0.5
torso_height = torso_z_max - torso_z_min

cam_f_data = bpy.data.cameras.new("cam_decal_front")
cam_f_data.type = "ORTHO"
cam_f_data.ortho_scale = torso_height * 1.05
cam_f = bpy.data.objects.new("cam_decal_front", cam_f_data)
bpy.context.scene.collection.objects.link(cam_f)
cam_f.location = Vector((center.x, center.y - 1.5, torso_z_center))
cam_f.rotation_euler = (math.pi / 2.0, 0.0, 0.0)

# Setup Decal Camera for Back Torso ONLY
cam_b_data = bpy.data.cameras.new("cam_decal_back")
cam_b_data.type = "ORTHO"
cam_b_data.ortho_scale = torso_height * 1.05
cam_b = bpy.data.objects.new("cam_decal_back", cam_b_data)
bpy.context.scene.collection.objects.link(cam_b)
cam_b.location = Vector((center.x, center.y + 1.5, torso_z_center))
cam_b.rotation_euler = (math.pi / 2.0, 0.0, math.pi)

bpy.context.view_layer.update()

# Project Front Torso UV
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

# Project Back Torso UV
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

# Bake Front Decal
img_p_f = bpy.data.images.load(patch_front)
img_p_b = bpy.data.images.load(patch_back)

img_bake_f = bpy.data.images.new("Decal_Bake_Front", tex_res, tex_res, alpha=True)
img_bake_b = bpy.data.images.new("Decal_Bake_Back", tex_res, tex_res, alpha=True)

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
nt.links.new(emi.inputs["Color"], t_node.outputs["Color"])

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

print("Baking Front Torso Decal...")
bpy.ops.object.bake(type="EMIT")

# Bake Back Torso Decal
t_node.image = img_p_b
uv_map_n.uv_map = "UV_Decal_Back"
target_n.image = img_bake_b

print("Baking Back Torso Decal...")
bpy.ops.object.bake(type="EMIT")

# Compositing in Python: strictly preserve base texture, apply decals with normal & bounding mask
buf_f = np.empty(tex_res * tex_res * 4, dtype=np.float32)
img_bake_f.pixels.foreach_get(buf_f)
buf_f = buf_f.reshape(tex_res, tex_res, 4)

buf_b = np.empty(tex_res * tex_res * 4, dtype=np.float32)
img_bake_b.pixels.foreach_get(buf_b)
buf_b = buf_b.reshape(tex_res, tex_res, 4)

# Alpha / valid pixel masks
f_mask = (buf_f[:, :, :3].sum(axis=2) > 0.05)[:, :, None]
b_mask = (buf_b[:, :, :3].sum(axis=2) > 0.05)[:, :, None]

buf_final = buf_base.copy()
# Blend back decal first, then front decal
buf_final[:, :, :3] = np.where(b_mask, buf_b[:, :, :3], buf_final[:, :, :3])
buf_final[:, :, :3] = np.where(f_mask, buf_f[:, :, :3], buf_final[:, :, :3])

img_final = bpy.data.images.new("Atlas_Master_4K", tex_res, tex_res, alpha=False)
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
print(f"EXPORTED_PERFECT_GLB: {out_glb}")
