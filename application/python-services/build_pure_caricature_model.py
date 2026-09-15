import bpy
import bmesh
import math
from mathutils import Vector

REF_IMG_PATH = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_reference.png"
INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
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
    
    # Forearm
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

# Projection Cameras
verts = [body_obj.matrix_world @ v.co for v in body_obj.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn

# 1. Front Head Projection Camera (Front of Face)
# Head bounds: z: 0.44 to 0.76, Center around (0, -0.02, 0.60), scale 0.35
cam_head = bpy.data.objects.new("CamHead", bpy.data.cameras.new("CamHead"))
cam_head.data.type = 'ORTHO'
cam_head.data.ortho_scale = 0.34
cam_head.location = Vector((0.0, -1.5, 0.60))
cam_head.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_head)

# 2. Torso Front Decal Projection Camera
torso_z = center.z + size.z * 0.08
ortho_s = 0.44
cam_f = bpy.data.objects.new("CamProjF", bpy.data.cameras.new("CamProjF"))
cam_f.data.type = 'ORTHO'
cam_f.data.ortho_scale = ortho_s
cam_f.location = Vector((center.x, center.y - 2.0, torso_z + 0.02))
cam_f.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_f)

# 3. Torso Back Decal Projection Camera
cam_b = bpy.data.objects.new("CamProjB", bpy.data.cameras.new("CamProjB"))
cam_b.data.type = 'ORTHO'
cam_b.data.ortho_scale = ortho_s
cam_b.location = Vector((center.x, center.y + 2.0, torso_z + 0.02))
cam_b.rotation_euler = (math.pi / 2.0, 0, math.pi)
bpy.context.scene.collection.objects.link(cam_b)

# Apply UV projections
uv_face = body_obj.data.uv_layers.new(name="UV_Face_Front")
mod_face = body_obj.modifiers.new("UVProjFace", 'UV_PROJECT')
mod_face.uv_layer = "UV_Face_Front"
mod_face.projector_count = 1
mod_face.projectors[0].object = cam_head
bpy.ops.object.modifier_apply(modifier="UVProjFace")

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

# --- MASTER PBR MATERIALS ---

# 1. Material Face (Front projection from reference image)
mat_face = bpy.data.materials.new(name="Material_Face")
mat_face.use_nodes = True
nh = mat_face.node_tree.nodes
nh.clear()
out_h = nh.new("ShaderNodeOutputMaterial")
bsdf_h = nh.new("ShaderNodeBsdfPrincipled")
tex_ref_img = nh.new("ShaderNodeTexImage")
tex_ref_img.image = bpy.data.images.load(REF_IMG_PATH)
tex_ref_img.extension = 'CLIP'
uv_face_node = nh.new("ShaderNodeUVMap")
uv_face_node.uv_map = "UV_Face_Front"
bsdf_h.inputs["Roughness"].default_value = 0.42
mat_face.node_tree.links.new(uv_face_node.outputs["UV"], tex_ref_img.inputs["Vector"])
mat_face.node_tree.links.new(tex_ref_img.outputs["Color"], bsdf_h.inputs["Base Color"])
mat_face.node_tree.links.new(bsdf_h.outputs["BSDF"], out_h.inputs["Surface"])

# 2. Material Hair (Deep Dark Espresso Afro Curls)
mat_hair = bpy.data.materials.new(name="Material_Hair")
mat_hair.use_nodes = True
nhr = mat_hair.node_tree.nodes
nhr.clear()
out_hr = nhr.new("ShaderNodeOutputMaterial")
bsdf_hr = nhr.new("ShaderNodeBsdfPrincipled")
bsdf_hr.inputs["Base Color"].default_value = (0.025, 0.015, 0.008, 1.0)
bsdf_hr.inputs["Roughness"].default_value = 0.85
mat_hair.node_tree.links.new(bsdf_hr.outputs["BSDF"], out_hr.inputs["Surface"])

# 3. Material Skin Arms (Warm Golden-Caramel Métis with SSS)
mat_skin = bpy.data.materials.new(name="Material_Skin_Arms")
mat_skin.use_nodes = True
ns = mat_skin.node_tree.nodes
ns.clear()
out_s = ns.new("ShaderNodeOutputMaterial")
bsdf_s = ns.new("ShaderNodeBsdfPrincipled")
bsdf_s.inputs["Base Color"].default_value = (0.64, 0.26, 0.10, 1.0)
bsdf_s.inputs["Roughness"].default_value = 0.42
if "Subsurface Weight" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface Weight"].default_value = 0.22
    if "Subsurface Radius" in bsdf_s.inputs:
        bsdf_s.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.25)
elif "Subsurface" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface"].default_value = 0.22
mat_skin.node_tree.links.new(bsdf_s.outputs["BSDF"], out_s.inputs["Surface"])

# 4. Material Front T-Shirt Graphic 4K
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

# 5. Material Back T-Shirt Graphic 4K
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

# 6. Material Denim Jeans (Realistic Indigo Denim)
mat_jeans = bpy.data.materials.new(name="Material_Jeans")
mat_jeans.use_nodes = True
nj = mat_jeans.node_tree.nodes
nj.clear()
out_j = nj.new("ShaderNodeOutputMaterial")
bsdf_j = nj.new("ShaderNodeBsdfPrincipled")
bsdf_j.inputs["Base Color"].default_value = (0.026, 0.086, 0.250, 1.0)
bsdf_j.inputs["Roughness"].default_value = 0.68
mat_jeans.node_tree.links.new(bsdf_j.outputs["BSDF"], out_j.inputs["Surface"])

# 7. Material Shoes (Satin Black Sneakers)
mat_shoes = bpy.data.materials.new(name="Material_Shoes")
mat_shoes.use_nodes = True
ne = mat_shoes.node_tree.nodes
ne.clear()
out_e = ne.new("ShaderNodeOutputMaterial")
bsdf_e = ne.new("ShaderNodeBsdfPrincipled")
bsdf_e.inputs["Base Color"].default_value = (0.015, 0.015, 0.015, 1.0)
bsdf_e.inputs["Roughness"].default_value = 0.38
mat_shoes.node_tree.links.new(bsdf_e.outputs["BSDF"], out_e.inputs["Surface"])

# 8. Material Black T-Shirt Fabric (Shoulders, Collar, Sleeves & Hem)
mat_shirt_fabric = bpy.data.materials.new(name="Material_TShirt_Fabric")
mat_shirt_fabric.use_nodes = True
nt = mat_shirt_fabric.node_tree.nodes
nt.clear()
out_t = nt.new("ShaderNodeOutputMaterial")
bsdf_t = nt.new("ShaderNodeBsdfPrincipled")
bsdf_t.inputs["Base Color"].default_value = (0.012, 0.012, 0.012, 1.0)
bsdf_t.inputs["Roughness"].default_value = 0.58
mat_shirt_fabric.node_tree.links.new(bsdf_t.outputs["BSDF"], out_t.inputs["Surface"])

# Assign Material Slots to Mesh
body_obj.data.materials.clear()
body_obj.data.materials.append(mat_face)         # 0: Face (Front Projection)
body_obj.data.materials.append(mat_hair)         # 1: Hair (Espresso curls)
body_obj.data.materials.append(mat_skin)         # 2: Arms & Hands
body_obj.data.materials.append(mat_front)        # 3: Front Decal 4K
body_obj.data.materials.append(mat_back)         # 4: Back Decal 4K
body_obj.data.materials.append(mat_jeans)        # 5: Denim Jeans
body_obj.data.materials.append(mat_shoes)        # 6: Black Sneakers
body_obj.data.materials.append(mat_shirt_fabric) # 7: T-Shirt Black Fabric

for poly in body_obj.data.polygons:
    p_verts = [body_obj.matrix_world @ body_obj.data.vertices[vi].co for vi in poly.vertices]
    avg_z = sum(v.z for v in p_verts) / len(p_verts)
    avg_x = sum(v.x for v in p_verts) / len(p_verts)
    avg_y = sum(v.y for v in p_verts) / len(p_verts)
    norm = poly.normal
    
    # 1. Arms & Hands
    if abs(avg_x) > 0.355:
        poly.material_index = 2
        continue
        
    # 2. Hair (Dome & curls)
    if avg_z > 0.72:
        poly.material_index = 1
        continue
    if avg_z > 0.52 and avg_y > 0.02:
        poly.material_index = 1 # Back/sides of head hair
        continue
        
    # 3. Face (Front of Face, Eyes, Nose, Lips, Cheeks, Ears)
    if 0.48 < avg_z <= 0.72 and abs(avg_x) < 0.22 and avg_y <= 0.02:
        poly.material_index = 0 # Face
        continue
        
    # 4. Neck skin / underside
    if 0.44 < avg_z <= 0.48 and abs(avg_x) < 0.08:
        poly.material_index = 2 # Golden skin
        continue
        
    # 5. Shoes (Sneakers)
    if avg_z <= -0.72:
        poly.material_index = 6
        continue
        
    # 6. Jeans (from waistline z = -0.14 down to ankles)
    if -0.72 < avg_z <= -0.14:
        poly.material_index = 5
        continue
        
    # 7. Torso / T-Shirt (from collar down to waistline z = -0.14)
    if -0.14 < avg_z <= 0.48:
        if abs(avg_x) < 0.22 and avg_z <= 0.42:
            if norm.y < -0.20:
                poly.material_index = 3 # Front Graphic
                continue
            elif norm.y > 0.20:
                poly.material_index = 4 # Back Graphic
                continue
        poly.material_index = 7 # Shirt Fabric (Black)
        continue

for c in [cam_head, cam_f, cam_b]:
    bpy.data.objects.remove(c, do_unlink=True)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)
print("SUCCESS_CLEAN_CARICATURE_GLB_EXPORTED!")
