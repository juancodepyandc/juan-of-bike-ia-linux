import bpy
import bmesh
import math
import random
import os
from mathutils import Vector, Euler, Matrix

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png"
FEMALE_TSHIRT = "/home/juan/AuroraIA/application/output/3d/avatar_femelle_tshirt_graphic_4k.png"
OUT_GLB = "/home/juan/AuroraIA/application/output/3d/avatar_femelle_vizion_master_final.glb"

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

# Morph body mesh slightly for elegant female stylized silhouette (slimmer waist, slightly softer jaw)
for v in bm.verts:
    # Slimmer waistline (-0.14 < z < 0.20)
    if -0.14 < v.co.z < 0.20:
        factor = 1.0 - 0.08 * math.sin(((v.co.z - (-0.14)) / 0.34) * math.pi)
        v.co.x *= factor
        v.co.y *= factor
    # Softer cheeks/jaw
    if 0.50 < v.co.z < 0.65 and v.co.y < 0.0:
        v.co.x *= 0.96

bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

# --- PART 1: FEMALE SLENDER SEAMLESS ARMS & 5-FINGER WELCOMING HANDS ---
def build_female_seamless_arm():
    bm = bmesh.new()
    
    profile = [
        (Vector((0.330,  0.032, 0.345)), 0.042, 0.040), # Sleeve Cuff
        (Vector((0.415,  0.016, 0.328)), 0.038, 0.036), # Upper Forearm
        (Vector((0.500,  0.002, 0.310)), 0.034, 0.032), # Mid Forearm
        (Vector((0.565, -0.008, 0.296)), 0.029, 0.025), # Pre-wrist
        (Vector((0.595, -0.012, 0.290)), 0.027, 0.022), # Slender Wrist joint
        (Vector((0.625, -0.016, 0.284)), 0.034, 0.021), # Palm base
        (Vector((0.655, -0.020, 0.278)), 0.038, 0.019), # Palm mid
        (Vector((0.680, -0.024, 0.272)), 0.036, 0.016), # Knuckle bridge
    ]
    
    rings = []
    num_sides = 24
    for i, (center, rz, ry) in enumerate(profile):
        ring_verts = []
        if i < len(profile) - 1:
            fwd = (profile[i+1][0] - center).normalized()
        else:
            fwd = (center - profile[i-1][0]).normalized()
            
        up = Vector((0, 0, 1))
        tang_z = (up - fwd * fwd.dot(up)).normalized()
        tang_y = fwd.cross(tang_z).normalized()
        
        for s in range(num_sides):
            angle = (s / num_sides) * 2.0 * math.pi
            offset = tang_z * (math.cos(angle) * rz) + tang_y * (math.sin(angle) * ry)
            v = bm.verts.new(center + offset)
            ring_verts.append(v)
        rings.append(ring_verts)
        
    for i in range(len(rings) - 1):
        r0 = rings[i]
        r1 = rings[i+1]
        for s in range(num_sides):
            s_next = (s + 1) % num_sides
            v00 = r0[s]
            v01 = r0[s_next]
            v11 = r1[s_next]
            v10 = r1[s]
            bm.faces.new([v00, v01, v11, v10])
            
    bm.faces.new(rings[0][::-1])
    
    p_tip_center = profile[-1][0] + Vector((0.012, -0.002, -0.003))
    v_tip = bm.verts.new(p_tip_center)
    for s in range(num_sides):
        s_next = (s + 1) % num_sides
        bm.faces.new([rings[-1][s], rings[-1][s_next], v_tip])
        
    mesh = bpy.data.meshes.new("FemaleArmSolidLoftMesh")
    bm.to_mesh(mesh)
    bm.free()
    
    arm_obj = bpy.data.objects.new("FemaleArmLoft", mesh)
    bpy.context.scene.collection.objects.link(arm_obj)
    
    hand_parts = [arm_obj]
    p_palm = Vector((0.638, -0.018, 0.281))
    
    # Thenar Eminence (Thumb base)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=20, ring_count=14, location=p_palm + Vector((-0.005, -0.008, 0.019)))
    thenar = bpy.context.active_object
    thenar.scale = (1.15, 0.80, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    hand_parts.append(thenar)
    
    # Hypothenar Eminence (Pinky base)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.015, segments=20, ring_count=14, location=p_palm + Vector((-0.005, -0.006, -0.015)))
    hypothenar = bpy.context.active_object
    hypothenar.scale = (1.10, 0.75, 0.95)
    bpy.ops.object.transform_apply(scale=True, location=True)
    hand_parts.append(hypothenar)
    
    # 5 Elegant Slender Fingers
    def add_slender_finger(p_base, p_mid, p_tip, r_base, r_mid, r_tip):
        segs = []
        for (p0, p1, r0, r1) in [(p_base, p_mid, r_base, r_mid), (p_mid, p_tip, r_mid, r_tip)]:
            v = p1 - p0
            l = v.length
            c = (p0 + p1) * 0.5
            f = v.normalized()
            r = Vector((0, 0, 1)).rotation_difference(f).to_euler()
            bpy.ops.mesh.primitive_cone_add(radius1=r0, radius2=r1, depth=l, vertices=16, location=c)
            cone = bpy.context.active_object
            cone.rotation_euler = r
            bpy.ops.object.transform_apply(location=True, rotation=True)
            segs.append(cone)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r_tip * 1.02, segments=16, ring_count=12, location=p_tip)
        sph = bpy.context.active_object
        segs.append(sph)
        return segs

    # Slender Thumb
    hand_parts.extend(add_slender_finger(
        p_palm + Vector((-0.004, -0.005, 0.020)),
        p_palm + Vector((0.019, -0.012, 0.054)),
        p_palm + Vector((0.044, -0.017, 0.082)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Slender Index
    hand_parts.extend(add_slender_finger(
        p_palm + Vector((0.035, -0.005, 0.020)),
        p_palm + Vector((0.074, -0.012, 0.028)),
        p_palm + Vector((0.112, -0.019, 0.034)),
        0.0110, 0.0095, 0.0075
    ))
    
    # Slender Middle
    hand_parts.extend(add_slender_finger(
        p_palm + Vector((0.038, -0.006, 0.006)),
        p_palm + Vector((0.080, -0.014, 0.008)),
        p_palm + Vector((0.122, -0.022, 0.010)),
        0.0115, 0.0100, 0.0080
    ))
    
    # Slender Ring
    hand_parts.extend(add_slender_finger(
        p_palm + Vector((0.036, -0.007, -0.008)),
        p_palm + Vector((0.075, -0.015, -0.012)),
        p_palm + Vector((0.114, -0.023, -0.015)),
        0.0110, 0.0095, 0.0075
    ))
    
    # Slender Pinky
    hand_parts.extend(add_slender_finger(
        p_palm + Vector((0.031, -0.008, -0.022)),
        p_palm + Vector((0.060, -0.017, -0.032)),
        p_palm + Vector((0.088, -0.025, -0.040)),
        0.0095, 0.0080, 0.0065
    ))
    
    bpy.ops.object.select_all(action='DESELECT')
    for p in hand_parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.join()
    
    arm_obj.data.remesh_voxel_size = 0.0011
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm_obj.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.88
    mod_s.iterations = 26
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    
    return arm_obj

arm_l = build_female_seamless_arm()
arm_l.name = "Female_Arm_Left"

# Right Arm (Mirrored along X)
bpy.ops.object.select_all(action='DESELECT')
arm_l.select_set(True)
bpy.context.view_layer.objects.active = arm_l
bpy.ops.object.duplicate()
arm_r = bpy.context.active_object
arm_r.name = "Female_Arm_Right"
arm_r.scale = (-1, 1, 1)
bpy.ops.object.transform_apply(scale=True)

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode='OBJECT')

# Join Body + Arm_L + Arm_R
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
arm_l.select_set(True)
arm_r.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# --- PART 2: FEMALE HIGH PUFF & CASCADING AFRO CURLS (1,400 MICRO-STRANDS) ---
def build_female_high_puff_curls():
    random.seed(2026)
    curl_objects = []
    
    # 1. High Top Puff Crown (Center: 0, 0.02, 0.845)
    puff_center = Vector((0.0, 0.015, 0.835))
    puff_rx, puff_ry, puff_rz = 0.110, 0.118, 0.105
    
    for c_idx in range(160):
        theta = random.uniform(0.05, 0.48 * math.pi)
        phi = random.uniform(0, 2 * math.pi)
        
        gx = puff_center.x + puff_rx * math.sin(theta) * math.cos(phi)
        gy = puff_center.y + puff_ry * math.sin(theta) * math.sin(phi)
        gz = puff_center.z + puff_rz * math.cos(theta)
        
        norm = (Vector((gx, gy, gz)) - puff_center).normalized()
        up = Vector((0, 0, 1))
        if abs(norm.dot(up)) > 0.9:
            up = Vector((0, 1, 0))
        tang = norm.cross(up).normalized()
        bitang = norm.cross(tang).normalized()
        
        cluster_turns = random.uniform(4.0, 6.5)
        cluster_rad = random.uniform(0.006, 0.012)
        cluster_len = random.uniform(0.025, 0.042)
        
        for s_idx in range(5):
            strand_angle_offset = (s_idx / 5.0) * 2.0 * math.pi + random.uniform(-0.3, 0.3)
            strand_radial_offset = random.uniform(0.001, 0.005)
            s_start = Vector((gx, gy, gz)) + tang * (math.cos(strand_angle_offset) * strand_radial_offset) + bitang * (math.sin(strand_angle_offset) * strand_radial_offset)
            
            curve_data = bpy.data.curves.new(name=f"PuffCurl_{c_idx}_{s_idx}", type='CURVE')
            curve_data.dimensions = '3D'
            curve_data.bevel_depth = random.uniform(0.0011, 0.0016)
            curve_data.bevel_resolution = 2
            
            spline = curve_data.splines.new('BEZIER')
            num_points = 14
            spline.bezier_points.add(num_points - 1)
            
            phase = random.uniform(0, 2 * math.pi)
            strand_turns = cluster_turns + random.uniform(-0.4, 0.4)
            strand_rad = cluster_rad * random.uniform(0.85, 1.15)
            strand_len = cluster_len * random.uniform(0.90, 1.10)
            
            for p_idx in range(num_points):
                t = p_idx / (num_points - 1)
                angle = t * strand_turns * 2.0 * math.pi + phase
                offset_t = math.cos(angle) * strand_rad * (0.6 + 0.6 * math.sin(t * math.pi))
                offset_b = math.sin(angle) * strand_rad * (0.6 + 0.6 * math.sin(t * math.pi))
                offset_n = t * strand_len
                pt_pos = s_start + tang * offset_t + bitang * offset_b + norm * offset_n
                bp = spline.bezier_points[p_idx]
                bp.co = pt_pos
                bp.handle_left_type = 'AUTO'
                bp.handle_right_type = 'AUTO'
                
            c_obj = bpy.data.objects.new(f"CurlObj_Puff_{c_idx}_{s_idx}", curve_data)
            bpy.context.scene.collection.objects.link(c_obj)
            curl_objects.append(c_obj)
            
    # 2. Cascading Side & Back Curls (Center: 0, -0.01, 0.710)
    base_center = Vector((0.0, -0.010, 0.705))
    base_rx, base_ry, base_rz = 0.124, 0.136, 0.118
    
    for c_idx in range(120):
        theta = random.uniform(0.12, 0.50 * math.pi)
        phi = random.uniform(0, 2 * math.pi)
        
        gx = base_center.x + base_rx * math.sin(theta) * math.cos(phi)
        gy = base_center.y + base_ry * math.sin(theta) * math.sin(phi)
        gz = base_center.z + base_rz * math.cos(theta)
        
        if gy < -0.01 and gz < 0.765:
            continue
        if abs(gx) > 0.14 and gz < 0.74:
            continue
            
        norm = (Vector((gx, gy, gz)) - base_center).normalized()
        up = Vector((0, 0, 1))
        if abs(norm.dot(up)) > 0.9:
            up = Vector((0, 1, 0))
        tang = norm.cross(up).normalized()
        bitang = norm.cross(tang).normalized()
        
        cluster_turns = random.uniform(3.5, 5.5)
        cluster_rad = random.uniform(0.005, 0.010)
        cluster_len = random.uniform(0.022, 0.035)
        
        for s_idx in range(5):
            strand_angle_offset = (s_idx / 5.0) * 2.0 * math.pi + random.uniform(-0.3, 0.3)
            strand_radial_offset = random.uniform(0.001, 0.004)
            s_start = Vector((gx, gy, gz)) + tang * (math.cos(strand_angle_offset) * strand_radial_offset) + bitang * (math.sin(strand_angle_offset) * strand_radial_offset)
            
            curve_data = bpy.data.curves.new(name=f"BaseCurl_{c_idx}_{s_idx}", type='CURVE')
            curve_data.dimensions = '3D'
            curve_data.bevel_depth = random.uniform(0.0010, 0.0015)
            curve_data.bevel_resolution = 2
            
            spline = curve_data.splines.new('BEZIER')
            num_points = 14
            spline.bezier_points.add(num_points - 1)
            
            phase = random.uniform(0, 2 * math.pi)
            strand_turns = cluster_turns + random.uniform(-0.4, 0.4)
            strand_rad = cluster_rad * random.uniform(0.85, 1.15)
            strand_len = cluster_len * random.uniform(0.90, 1.10)
            
            for p_idx in range(num_points):
                t = p_idx / (num_points - 1)
                angle = t * strand_turns * 2.0 * math.pi + phase
                offset_t = math.cos(angle) * strand_rad * (0.6 + 0.6 * math.sin(t * math.pi))
                offset_b = math.sin(angle) * strand_rad * (0.6 + 0.6 * math.sin(t * math.pi))
                offset_n = t * strand_len
                pt_pos = s_start + tang * offset_t + bitang * offset_b + norm * offset_n
                bp = spline.bezier_points[p_idx]
                bp.co = pt_pos
                bp.handle_left_type = 'AUTO'
                bp.handle_right_type = 'AUTO'
                
            c_obj = bpy.data.objects.new(f"CurlObj_Base_{c_idx}_{s_idx}", curve_data)
            bpy.context.scene.collection.objects.link(c_obj)
            curl_objects.append(c_obj)
            
    bpy.ops.object.select_all(action='DESELECT')
    for c in curl_objects:
        c.select_set(True)
    bpy.context.view_layer.objects.active = curl_objects[0]
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.join()
    
    hair_mesh = bpy.context.active_object
    hair_mesh.name = "FemaleHighPuffAfroHairMesh"
    return hair_mesh

female_hair_obj = build_female_high_puff_curls()

# Join Hair with Body Object
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
female_hair_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# --- PART 3: PROJECTION CAMERAS & MULTI-MATERIAL PBR SHADERS ---
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

# --- MASTER PBR MATERIALS ---

# 1. Material Head (100% Golden Métis Skin)
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

# 2. Material Hair (Rich Espresso Melanin Curls)
mat_hair = bpy.data.materials.new(name="Material_Hair")
mat_hair.use_nodes = True
nhr = mat_hair.node_tree.nodes
nhr.clear()
out_hr = nhr.new("ShaderNodeOutputMaterial")
bsdf_hr = nhr.new("ShaderNodeBsdfPrincipled")
bsdf_hr.inputs["Base Color"].default_value = (0.006, 0.003, 0.001, 1.0)
bsdf_hr.inputs["Roughness"].default_value = 0.95
if "Specular IOR Level" in bsdf_hr.inputs:
    bsdf_hr.inputs["Specular IOR Level"].default_value = 0.02
elif "Specular" in bsdf_hr.inputs:
    bsdf_hr.inputs["Specular"].default_value = 0.02
mat_hair.node_tree.links.new(bsdf_hr.outputs["BSDF"], out_hr.inputs["Surface"])

# 3. Material Skin Arms (Feminine Golden Caramel Métis)
mat_skin = bpy.data.materials.new(name="Material_Skin_Arms")
mat_skin.use_nodes = True
ns = mat_skin.node_tree.nodes
ns.clear()
out_s = ns.new("ShaderNodeOutputMaterial")
bsdf_s = ns.new("ShaderNodeBsdfPrincipled")
bsdf_s.inputs["Base Color"].default_value = (0.64, 0.26, 0.10, 1.0)
bsdf_s.inputs["Roughness"].default_value = 0.42
if "Subsurface Weight" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface Weight"].default_value = 0.25
    if "Subsurface Radius" in bsdf_s.inputs:
        bsdf_s.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.25)
elif "Subsurface" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface"].default_value = 0.25
mat_skin.node_tree.links.new(bsdf_s.outputs["BSDF"], out_s.inputs["Surface"])

# 4. Material Female T-Shirt Graphic 4K (AURORA CREATIVE AI Cyberpunk Sunset)
mat_tshirt_graphic = bpy.data.materials.new(name="Material_Female_TShirt_Graphic")
mat_tshirt_graphic.use_nodes = True
nf = mat_tshirt_graphic.node_tree.nodes
nf.clear()
out_f = nf.new("ShaderNodeOutputMaterial")
bsdf_f = nf.new("ShaderNodeBsdfPrincipled")
tex_f_img = nf.new("ShaderNodeTexImage")
tex_f_img.image = bpy.data.images.load(FEMALE_TSHIRT)
tex_f_img.extension = 'CLIP'
uv_f_node = nf.new("ShaderNodeUVMap")
uv_f_node.uv_map = "UV_Front"
bsdf_f.inputs["Roughness"].default_value = 0.46
mat_tshirt_graphic.node_tree.links.new(uv_f_node.outputs["UV"], tex_f_img.inputs["Vector"])
mat_tshirt_graphic.node_tree.links.new(tex_f_img.outputs["Color"], bsdf_f.inputs["Base Color"])
mat_tshirt_graphic.node_tree.links.new(bsdf_f.outputs["BSDF"], out_f.inputs["Surface"])

# 5. Material Dark Denim Jeans
mat_jeans = bpy.data.materials.new(name="Material_Jeans")
mat_jeans.use_nodes = True
nj = mat_jeans.node_tree.nodes
nj.clear()
out_j = nj.new("ShaderNodeOutputMaterial")
bsdf_j = nj.new("ShaderNodeBsdfPrincipled")
bsdf_j.inputs["Base Color"].default_value = (0.018, 0.045, 0.120, 1.0)
bsdf_j.inputs["Roughness"].default_value = 0.65
mat_jeans.node_tree.links.new(bsdf_j.outputs["BSDF"], out_j.inputs["Surface"])

# 6. Material Shoes (Streetwear Sneakers)
mat_shoes = bpy.data.materials.new(name="Material_Shoes")
mat_shoes.use_nodes = True
ne = mat_shoes.node_tree.nodes
ne.clear()
out_e = ne.new("ShaderNodeOutputMaterial")
bsdf_e = ne.new("ShaderNodeBsdfPrincipled")
bsdf_e.inputs["Base Color"].default_value = (0.015, 0.015, 0.015, 1.0)
bsdf_e.inputs["Roughness"].default_value = 0.38
mat_shoes.node_tree.links.new(bsdf_e.outputs["BSDF"], out_e.inputs["Surface"])

# 7. Material T-Shirt Fabric Dark Purple/Navy (#120B1E)
mat_shirt_fabric = bpy.data.materials.new(name="Material_Female_TShirt_Fabric")
mat_shirt_fabric.use_nodes = True
nt = mat_shirt_fabric.node_tree.nodes
nt.clear()
out_t = nt.new("ShaderNodeOutputMaterial")
bsdf_t = nt.new("ShaderNodeBsdfPrincipled")
bsdf_t.inputs["Base Color"].default_value = (0.035, 0.020, 0.055, 1.0)
bsdf_t.inputs["Roughness"].default_value = 0.52
mat_shirt_fabric.node_tree.links.new(bsdf_t.outputs["BSDF"], out_t.inputs["Surface"])

# Assign Material Slots to Mesh
body_obj.data.materials.clear()
body_obj.data.materials.append(mat_head)           # 0: Head
body_obj.data.materials.append(mat_hair)           # 1: Hair (Espresso curls)
body_obj.data.materials.append(mat_skin)           # 2: Arms & Hands
body_obj.data.materials.append(mat_tshirt_graphic) # 3: Female Graphic T-Shirt 4K
body_obj.data.materials.append(mat_jeans)          # 4: Denim Jeans
body_obj.data.materials.append(mat_shoes)          # 5: Sneakers
body_obj.data.materials.append(mat_shirt_fabric)   # 6: T-Shirt Fabric

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
        
    # 2. Ears -> 100% Skin
    if abs(avg_x) > 0.14 and 0.52 < avg_z < 0.74:
        poly.material_index = 0
        continue
        
    # 3. Face, Eyes, Nose, Lips, Cheeks
    if avg_z > 0.48 and abs(avg_x) <= 0.14 and avg_y < 0.04 and avg_z <= 0.775:
        poly.material_index = 0
        continue
        
    # 4. Hair (Scalp Dome & High Puff Micro-Curls)
    if avg_z > 0.775 or (avg_z > 0.68 and avg_y >= 0.04):
        poly.material_index = 1
        continue
        
    # 5. Back of neck below hair
    if avg_z > 0.48 and abs(avg_x) < 0.25:
        poly.material_index = 0
        continue
        
    # 6. Shoes (Sneakers)
    if avg_z <= -0.72:
        poly.material_index = 5
        continue
        
    # 7. Jeans
    if -0.72 < avg_z <= -0.14:
        poly.material_index = 4
        continue
        
    # 8. Torso / T-Shirt
    if -0.14 < avg_z <= 0.48:
        if abs(avg_x) < 0.22 and avg_z <= 0.42:
            if norm.y < -0.20 or norm.y > 0.20:
                poly.material_index = 3 # Graphic Print
                continue
        poly.material_index = 6 # Shirt Fabric
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
print("SUCCESS_FEMALE_AVATAR_MASTERPIECE_GLB_EXPORTED!")
