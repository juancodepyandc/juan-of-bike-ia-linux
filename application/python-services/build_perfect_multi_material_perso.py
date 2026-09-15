import bpy
import bmesh
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
FRONT_DECAL = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
BACK_DECAL = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
OUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj

# Cut old arm vertices outside sleeve cuff (x > 0.355)
bm = bmesh.new()
bm.from_mesh(body_obj.data)
verts_to_del = [v for v in bm.verts if abs(v.co.x) > 0.355]
bmesh.ops.delete(bm, geom=verts_to_del, context='VERTS')
bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

# Build Caricature Arms & 5-Finger Hands
def build_flawless_arm_and_hand():
    parts = []
    
    # Forearm: smoothly tapers from sleeve (r=0.048) to wrist (r=0.042)
    p_sleeve = Vector((0.330, 0.035, 0.354))
    p_wrist  = Vector((0.600, -0.015, 0.295))
    p_palm   = Vector((0.640, -0.025, 0.285))
    
    vec_arm = p_wrist - p_sleeve
    len_arm = vec_arm.length
    center_arm = (p_sleeve + p_wrist) * 0.5
    fwd_arm = vec_arm.normalized()
    rot_arm = Vector((0, 0, 1)).rotation_difference(fwd_arm).to_euler()
    
    bpy.ops.mesh.primitive_cone_add(radius1=0.048, radius2=0.042, depth=len_arm, vertices=32, location=center_arm)
    forearm = bpy.context.active_object
    forearm.rotation_euler = rot_arm
    bpy.ops.object.transform_apply(location=True, rotation=True)
    parts.append(forearm)
    
    # Wrist blend sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.043, segments=24, ring_count=16, location=p_wrist)
    wrist_sph = bpy.context.active_object
    wrist_sph.scale = (1.10, 0.70, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(wrist_sph)
    
    # Palm
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.046, segments=24, ring_count=16, location=p_palm)
    palm = bpy.context.active_object
    palm.scale = (1.20, 0.55, 1.10)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(palm)
    
    # Thenar
    p_thenar = p_palm + Vector((-0.010, 0.012, 0.028))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, segments=20, ring_count=14, location=p_thenar)
    thenar = bpy.context.active_object
    thenar.scale = (1.15, 0.80, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(thenar)
    
    # 5 Fingers
    def add_capsule(p_start, p_end, r_start, r_end):
        vec = p_end - p_start
        length = vec.length
        center = (p_start + p_end) * 0.5
        fwd = vec.normalized()
        rot = Vector((0, 0, 1)).rotation_difference(fwd).to_euler()
        
        bpy.ops.mesh.primitive_cone_add(radius1=r_start, radius2=r_end, depth=length, vertices=16, location=center)
        cone = bpy.context.active_object
        cone.rotation_euler = rot
        bpy.ops.object.transform_apply(location=True, rotation=True)
        
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r_end*1.02, segments=16, ring_count=12, location=p_end)
        sph = bpy.context.active_object
        return [cone, sph]
        
    finger_chains = [
        ("Thumb",  p_palm + Vector((-0.010, 0.012, 0.030)), p_palm + Vector((0.018, 0.018, 0.070)), p_palm + Vector((0.048, 0.022, 0.098)), 0.0175, 0.0130),
        ("Index",  p_palm + Vector((0.030, 0.002, 0.026)),  p_palm + Vector((0.076, -0.002, 0.036)), p_palm + Vector((0.118, -0.004, 0.044)), 0.0140, 0.0105),
        ("Middle", p_palm + Vector((0.034, 0.001, 0.008)),  p_palm + Vector((0.088, -0.003, 0.010)), p_palm + Vector((0.134, -0.005, 0.012)), 0.0145, 0.0110),
        ("Ring",   p_palm + Vector((0.031, 0.000, -0.010)), p_palm + Vector((0.080, -0.004, -0.015)), p_palm + Vector((0.122, -0.006, -0.018)), 0.0140, 0.0105),
        ("Pinky",  p_palm + Vector((0.024, -0.002, -0.026)), p_palm + Vector((0.064, -0.005, -0.040)), p_palm + Vector((0.096, -0.007, -0.050)), 0.0125, 0.0090),
    ]
    
    for name, p_root, p_knuckle, p_tip, r_base, r_tip in finger_chains:
        r_mid = (r_base + r_tip) * 0.5
        parts.extend(add_capsule(p_root, p_knuckle, r_base, r_mid))
        parts.extend(add_capsule(p_knuckle, p_tip, r_mid, r_tip))
        
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = forearm
    bpy.ops.object.join()
    
    arm = bpy.context.active_object
    arm.name = "UnifiedArmAndHand"
    arm.data.remesh_voxel_size = 0.0016
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.80
    mod_s.iterations = 18
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    return arm

arm_l = build_flawless_arm_and_hand()
arm_l.name = "Arm_Left"

bpy.ops.object.select_all(action='DESELECT')
arm_l.select_set(True)
bpy.context.view_layer.objects.active = arm_l
bpy.ops.object.duplicate()
arm_r = bpy.context.active_object
arm_r.name = "Arm_Right"
arm_r.scale = (-1, 1, 1)
bpy.ops.object.transform_apply(scale=True)

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
arm_l.select_set(True)
arm_r.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# Setup Projection Cameras for T-Shirt Decals
verts = [body_obj.matrix_world @ v.co for v in body_obj.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn
torso_z = center.z + size.z * 0.08
ortho_s = 0.44

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

uv_front = body_obj.data.uv_layers.new(name="UV_Front")
mod_f = body_obj.modifiers.new("UVProjF", 'UV_PROJECT')
mod_f.uv_layer = "UV_Front"
mod_f.projector_count = 1
mod_f.projectors[0].object = cam_f
bpy.ops.object.modifier_apply(modifier="UVProjF")

uv_back = body_obj.data.uv_layers.new(name="UV_Back")
mod_b = body_obj.modifiers.new("UVProjB", 'UV_PROJECT')
mod_b.uv_layer = "UV_Back"
mod_b.projector_count = 1
mod_b.projectors[0].object = cam_b
bpy.ops.object.modifier_apply(modifier="UVProjB")

# --- CREATE DEDICATED FLAWLESS MATERIALS ---

# 1. Material Head (Face, Eyes, Lips, Hair)
mat_head = bpy.data.materials.new(name="Material_Head")
mat_head.use_nodes = True
nh = mat_head.node_tree.nodes
nh.clear()
out_h = nh.new("ShaderNodeOutputMaterial")
bsdf_h = nh.new("ShaderNodeBsdfPrincipled")
tex_h = nh.new("ShaderNodeTexImage")
tex_h.image = bpy.data.images.load(BASE_TEX)
bsdf_h.inputs["Roughness"].default_value = 0.44
mat_head.node_tree.links.new(tex_h.outputs["Color"], bsdf_h.inputs["Base Color"])
mat_head.node_tree.links.new(bsdf_h.outputs["BSDF"], out_h.inputs["Surface"])

# 2. Material Skin Arms (Unified Golden Métis)
mat_skin = bpy.data.materials.new(name="Material_Skin_Arms")
mat_skin.use_nodes = True
ns = mat_skin.node_tree.nodes
ns.clear()
out_s = ns.new("ShaderNodeOutputMaterial")
bsdf_s = ns.new("ShaderNodeBsdfPrincipled")
# Warm Golden-Caramel Métis Skin (#C68050 / Linear: 0.56, 0.22, 0.08)
bsdf_s.inputs["Base Color"].default_value = (0.56, 0.22, 0.08, 1.0)
bsdf_s.inputs["Roughness"].default_value = 0.42
if "Subsurface Weight" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface Weight"].default_value = 0.20
elif "Subsurface" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface"].default_value = 0.20
mat_skin.node_tree.links.new(bsdf_s.outputs["BSDF"], out_s.inputs["Surface"])

# 3. Material Front T-Shirt Graphic 4K
mat_front = bpy.data.materials.new(name="Material_Front_Graphic")
mat_front.use_nodes = True
nf = mat_front.node_tree.nodes
nf.clear()
out_f = nf.new("ShaderNodeOutputMaterial")
bsdf_f = nf.new("ShaderNodeBsdfPrincipled")
tex_f_img = nf.new("ShaderNodeTexImage")
tex_f_img.image = bpy.data.images.load(FRONT_DECAL)
tex_f_img.extension = 'CLIP'
uv_f_node = nf.new("ShaderNodeUVMap")
uv_f_node.uv_map = "UV_Front"
bsdf_f.inputs["Roughness"].default_value = 0.48
mat_front.node_tree.links.new(uv_f_node.outputs["UV"], tex_f_img.inputs["Vector"])
mat_front.node_tree.links.new(tex_f_img.outputs["Color"], bsdf_f.inputs["Base Color"])
mat_front.node_tree.links.new(bsdf_f.outputs["BSDF"], out_f.inputs["Surface"])

# 4. Material Back T-Shirt Graphic 4K
mat_back = bpy.data.materials.new(name="Material_Back_Graphic")
mat_back.use_nodes = True
nk = mat_back.node_tree.nodes
nk.clear()
out_k = nk.new("ShaderNodeOutputMaterial")
bsdf_k = nk.new("ShaderNodeBsdfPrincipled")
tex_k_img = nk.new("ShaderNodeTexImage")
tex_k_img.image = bpy.data.images.load(BACK_DECAL)
tex_k_img.extension = 'CLIP'
uv_k_node = nk.new("ShaderNodeUVMap")
uv_k_node.uv_map = "UV_Back"
bsdf_k.inputs["Roughness"].default_value = 0.48
mat_back.node_tree.links.new(uv_k_node.outputs["UV"], tex_k_img.inputs["Vector"])
mat_back.node_tree.links.new(tex_k_img.outputs["Color"], bsdf_k.inputs["Base Color"])
mat_back.node_tree.links.new(bsdf_k.outputs["BSDF"], out_k.inputs["Surface"])

# 5. Material Denim Jeans (Rich Medium-Blue Denim)
mat_jeans = bpy.data.materials.new(name="Material_Jeans")
mat_jeans.use_nodes = True
nj = mat_jeans.node_tree.nodes
nj.clear()
out_j = nj.new("ShaderNodeOutputMaterial")
bsdf_j = nj.new("ShaderNodeBsdfPrincipled")
# Pure vibrant medium-blue denim (#325896 -> Linear: 0.032, 0.102, 0.312)
bsdf_j.inputs["Base Color"].default_value = (0.035, 0.110, 0.320, 1.0)
bsdf_j.inputs["Roughness"].default_value = 0.65
mat_jeans.node_tree.links.new(bsdf_j.outputs["BSDF"], out_j.inputs["Surface"])

# 6. Material Shoes (Clean Satin Black Sneakers)
mat_shoes = bpy.data.materials.new(name="Material_Shoes")
mat_shoes.use_nodes = True
ne = mat_shoes.node_tree.nodes
ne.clear()
out_e = ne.new("ShaderNodeOutputMaterial")
bsdf_e = ne.new("ShaderNodeBsdfPrincipled")
# Satin Black Nike Air Force (#141414 -> Linear: 0.015, 0.015, 0.015)
bsdf_e.inputs["Base Color"].default_value = (0.015, 0.015, 0.015, 1.0)
bsdf_e.inputs["Roughness"].default_value = 0.40
mat_shoes.node_tree.links.new(bsdf_e.outputs["BSDF"], out_e.inputs["Surface"])

# 7. Material Black T-Shirt Fabric (Shoulders & Sleeves)
mat_shirt_fabric = bpy.data.materials.new(name="Material_TShirt_Fabric")
mat_shirt_fabric.use_nodes = True
nt = mat_shirt_fabric.node_tree.nodes
nt.clear()
out_t = nt.new("ShaderNodeOutputMaterial")
bsdf_t = nt.new("ShaderNodeBsdfPrincipled")
# Jet Black Cotton (#121212 -> Linear: 0.012, 0.012, 0.012)
bsdf_t.inputs["Base Color"].default_value = (0.012, 0.012, 0.012, 1.0)
bsdf_t.inputs["Roughness"].default_value = 0.58
mat_shirt_fabric.node_tree.links.new(bsdf_t.outputs["BSDF"], out_t.inputs["Surface"])

# Assign Material Slots to Mesh
body_obj.data.materials.clear()
body_obj.data.materials.append(mat_head)         # 0: Head (Face, Eyes, Mouth, Hair)
body_obj.data.materials.append(mat_skin)         # 1: Arms & Hands
body_obj.data.materials.append(mat_front)        # 2: Front T-Shirt Graphic 4K
body_obj.data.materials.append(mat_back)         # 3: Back T-Shirt Graphic 4K
body_obj.data.materials.append(mat_jeans)        # 4: Denim Jeans
body_obj.data.materials.append(mat_shoes)        # 5: Black Sneakers
body_obj.data.materials.append(mat_shirt_fabric) # 6: T-Shirt Black Fabric

# Precise Polygonal Assignment:
# - Arms & Hands: |x| > 0.355 -> mat_skin (1)
# - Head: z > 0.40 -> mat_head (0)
# - Front T-Shirt Decal: 0.02 < z < 0.38 and |x| < 0.20 and norm.y < -0.20 -> mat_front (2)
# - Back T-Shirt Decal: 0.02 < z < 0.38 and |x| < 0.20 and norm.y > 0.20 -> mat_back (3)
# - T-Shirt Base/Fabric: 0.02 < z < 0.40 (shoulders/sleeves/flanks) -> mat_shirt_fabric (6)
# - Denim Jeans: -0.72 < z <= 0.02 -> mat_jeans (4)
# - Black Sneakers: z <= -0.72 -> mat_shoes (5)

for poly in body_obj.data.polygons:
    p_verts = [body_obj.matrix_world @ body_obj.data.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    norm = poly.normal
    
    # 1. Arms & Hands
    if abs(avg_x) > 0.355:
        poly.material_index = 1
        continue
        
    # 2. Head (Face, Eyes, Hair, Ears, Neck)
    if avg_z > 0.40:
        poly.material_index = 0
        continue
        
    # 3. Shoes (Sneakers)
    if avg_z <= -0.72:
        poly.material_index = 5
        continue
        
    # 4. Jeans (Pants)
    if -0.72 < avg_z <= 0.02:
        poly.material_index = 4
        continue
        
    # 5. Torso / T-Shirt
    if 0.02 < avg_z <= 0.40:
        if 0.02 < avg_z < 0.38 and abs(avg_x) < 0.20:
            if norm.y < -0.20:
                poly.material_index = 2 # Front Graphic
                continue
            elif norm.y > 0.20:
                poly.material_index = 3 # Back Graphic
                continue
        poly.material_index = 6 # Shirt Fabric (Black)
        continue

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
print("SUCCESS_CLEAN_MULTI_MATERIAL_GLB_EXPORTED!")
