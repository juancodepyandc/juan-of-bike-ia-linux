import bpy
import bmesh
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
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

# Setup Cameras for UV Projection of Decals
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

# --- MATERIAL 0: CLOTHES & BODY BASE ---
mat_clothes = bpy.data.materials.new(name="Material_Clothes")
mat_clothes.use_nodes = True
nc = mat_clothes.node_tree.nodes
nc.clear()
out_c = nc.new("ShaderNodeOutputMaterial")
bsdf_c = nc.new("ShaderNodeBsdfPrincipled")
tex_c = nc.new("ShaderNodeTexImage")
tex_c.image = bpy.data.images.load(BASE_TEX)
bsdf_c.inputs["Roughness"].default_value = 0.55
mat_clothes.node_tree.links.new(tex_c.outputs["Color"], bsdf_c.inputs["Base Color"])
mat_clothes.node_tree.links.new(bsdf_c.outputs["BSDF"], out_c.inputs["Surface"])

# --- MATERIAL 1: AUTHENTIC GOLDEN-AMBER MÉTIS SKIN ---
mat_skin = bpy.data.materials.new(name="Material_Skin_Metis")
mat_skin.use_nodes = True
ns = mat_skin.node_tree.nodes
ns.clear()
out_s = ns.new("ShaderNodeOutputMaterial")
bsdf_s = ns.new("ShaderNodeBsdfPrincipled")
# Warm golden-amber caramel métis tone (#D88E5E / R:0.84, G:0.56, B:0.37)
bsdf_s.inputs["Base Color"].default_value = (0.76, 0.46, 0.28, 1.0)
bsdf_s.inputs["Roughness"].default_value = 0.44
# Subtle subsurface scattering for lifelike skin glow
if "Subsurface Weight" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface Weight"].default_value = 0.18
elif "Subsurface" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface"].default_value = 0.18
mat_skin.node_tree.links.new(bsdf_s.outputs["BSDF"], out_s.inputs["Surface"])

# --- MATERIAL 2: DEEP ESPRESSO CURLS HAIR ---
mat_hair = bpy.data.materials.new(name="Material_Hair")
mat_hair.use_nodes = True
nh = mat_hair.node_tree.nodes
nh.clear()
out_h = nh.new("ShaderNodeOutputMaterial")
bsdf_h = nh.new("ShaderNodeBsdfPrincipled")
# Deep dark chocolate espresso curls (#1A120B)
bsdf_h.inputs["Base Color"].default_value = (0.045, 0.028, 0.016, 1.0)
bsdf_h.inputs["Roughness"].default_value = 0.88
mat_hair.node_tree.links.new(bsdf_h.outputs["BSDF"], out_h.inputs["Surface"])

# --- MATERIAL 3: FRONT T-SHIRT DECAL 4K ---
mat_front = bpy.data.materials.new(name="Material_Front_Graphic")
mat_front.use_nodes = True
nf = mat_front.node_tree.nodes
nf.clear()
out_f = nf.new("ShaderNodeOutputMaterial")
bsdf_f = nf.new("ShaderNodeBsdfPrincipled")
tex_f_img = nf.new("ShaderNodeTexImage")
tex_f_img.image = bpy.data.images.load(FRONT_TEX)
tex_f_img.extension = 'CLIP'
uv_f_node = nf.new("ShaderNodeUVMap")
uv_f_node.uv_map = "UV_Front"
bsdf_f.inputs["Roughness"].default_value = 0.48
mat_front.node_tree.links.new(uv_f_node.outputs["UV"], tex_f_img.inputs["Vector"])
mat_front.node_tree.links.new(tex_f_img.outputs["Color"], bsdf_f.inputs["Base Color"])
mat_front.node_tree.links.new(bsdf_f.outputs["BSDF"], out_f.inputs["Surface"])

# --- MATERIAL 4: BACK T-SHIRT DECAL 4K ---
mat_back = bpy.data.materials.new(name="Material_Back_Graphic")
mat_back.use_nodes = True
nk = mat_back.node_tree.nodes
nk.clear()
out_k = nk.new("ShaderNodeOutputMaterial")
bsdf_k = nk.new("ShaderNodeBsdfPrincipled")
tex_k_img = nk.new("ShaderNodeTexImage")
tex_k_img.image = bpy.data.images.load(BACK_TEX)
tex_k_img.extension = 'CLIP'
uv_k_node = nk.new("ShaderNodeUVMap")
uv_k_node.uv_map = "UV_Back"
bsdf_k.inputs["Roughness"].default_value = 0.48
mat_back.node_tree.links.new(uv_k_node.outputs["UV"], tex_k_img.inputs["Vector"])
mat_back.node_tree.links.new(tex_k_img.outputs["Color"], bsdf_k.inputs["Base Color"])
mat_back.node_tree.links.new(bsdf_k.outputs["BSDF"], out_k.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat_clothes) # 0
ob.data.materials.append(mat_skin)    # 1
ob.data.materials.append(mat_hair)    # 2
ob.data.materials.append(mat_front)   # 3
ob.data.materials.append(mat_back)    # 4

# Assign Material Slots to Faces:
# - Arms/Hands (|x| > 0.35): Skin (1)
# - Face / Neck (0.42 <= z <= 0.81, not hair): Skin (1)
# - Hair (z > 0.81, or head undercut): Hair (2)
# - Front Graphic (0.02 < z < 0.38, |x| < 0.20, norm.y < -0.25): Graphic (3)
# - Back Graphic (0.02 < z < 0.38, |x| < 0.20, norm.y > 0.25): Graphic (4)
# - Jeans & Shoes & T-Shirt base: Clothes (0)

for poly in ob.data.polygons:
    p_verts = [ob.matrix_world @ ob.data.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    avg_y = sum(v.y for v in p_verts) / len(p_verts)
    norm = poly.normal
    
    # Decals
    if 0.02 < avg_z < 0.38 and abs(avg_x) < 0.20:
        if norm.y < -0.25:
            poly.material_index = 3
            continue
        elif norm.y > 0.25:
            poly.material_index = 4
            continue
            
    # Arms & Hands
    if abs(avg_x) > 0.35:
        poly.material_index = 1
        continue
        
    # Hair (Top afro curl dome z > 0.80)
    if avg_z > 0.80:
        poly.material_index = 2
        continue
        
    # Hair Undercut / Back of head
    if 0.65 <= avg_z <= 0.80 and avg_y > 0.02:
        poly.material_index = 2
        continue
        
    # Face, Cheeks, Ears, Neck, Forehead
    if 0.42 <= avg_z <= 0.80 and abs(avg_x) < 0.25:
        poly.material_index = 1
        continue
        
    # Rest is Clothes (Jeans, Shoes, T-Shirt body)
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
print("SUCCESS_DEDICATED_METIS_GLB_EXPORTED!")
