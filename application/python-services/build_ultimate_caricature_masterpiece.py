import bpy
import bmesh
import math
import random
from mathutils import Vector, Euler, Matrix

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
FRONT_DECAL = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
BACK_DECAL = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
OUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj

# Cut old arm vertices outside sleeve cuff (x > 0.355) and soften forehead ridge
bm = bmesh.new()
bm.from_mesh(body_obj.data)
verts_to_del = [v for v in bm.verts if abs(v.co.x) > 0.355]
bmesh.ops.delete(bm, geom=verts_to_del, context='VERTS')

for v in bm.verts:
    if 0.755 < v.co.z < 0.815 and v.co.y < -0.10 and abs(v.co.x) < 0.15:
        t = (v.co.z - 0.755) / (0.815 - 0.755)
        v.co.y = v.co.y * (1.0 - 0.18 * math.sin(t * math.pi)) + (-0.11) * (0.18 * math.sin(t * math.pi))

bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

# --- PART 1: 100% WATERTIGHT SOLID SEAMLESS ARM & 5-FINGER WELCOMING HAND ---
def build_seamless_caricature_arm():
    bm = bmesh.new()
    
    profile = [
        (Vector((0.330,  0.035, 0.354)), 0.048, 0.046), # Sleeve Cuff
        (Vector((0.420,  0.018, 0.334)), 0.045, 0.043), # Upper Forearm
        (Vector((0.510,  0.002, 0.314)), 0.041, 0.038), # Mid Forearm
        (Vector((0.575, -0.010, 0.298)), 0.036, 0.030), # Pre-wrist
        (Vector((0.605, -0.015, 0.292)), 0.034, 0.026), # Wrist joint
        (Vector((0.635, -0.020, 0.285)), 0.040, 0.026), # Palm base
        (Vector((0.665, -0.025, 0.278)), 0.044, 0.024), # Palm mid
        (Vector((0.690, -0.030, 0.272)), 0.042, 0.020), # Knuckle bridge
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
    
    p_tip_center = profile[-1][0] + Vector((0.015, -0.003, -0.004))
    v_tip = bm.verts.new(p_tip_center)
    for s in range(num_sides):
        s_next = (s + 1) % num_sides
        bm.faces.new([rings[-1][s], rings[-1][s_next], v_tip])
        
    mesh = bpy.data.meshes.new("ArmSolidLoftMesh")
    bm.to_mesh(mesh)
    bm.free()
    
    arm_obj = bpy.data.objects.new("ArmLoft", mesh)
    bpy.context.scene.collection.objects.link(arm_obj)
    
    hand_parts = [arm_obj]
    p_palm = Vector((0.645, -0.022, 0.282))
    
    # Thenar Eminence (Thumb base muscle on palm side -Y, +Z)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.022, segments=20, ring_count=14, location=p_palm + Vector((-0.006, -0.010, 0.022)))
    thenar = bpy.context.active_object
    thenar.scale = (1.20, 0.85, 1.10)
    bpy.ops.object.transform_apply(scale=True, location=True)
    hand_parts.append(thenar)
    
    # Hypothenar Eminence (Pinky base muscle on palm side -Y, -Z)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=20, ring_count=14, location=p_palm + Vector((-0.006, -0.008, -0.018)))
    hypothenar = bpy.context.active_object
    hypothenar.scale = (1.15, 0.80, 1.00)
    bpy.ops.object.transform_apply(scale=True, location=True)
    hand_parts.append(hypothenar)
    
    # 5 Fingers
    def add_finger(p_base, p_mid, p_tip, r_base, r_mid, r_tip):
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r_tip * 1.04, segments=16, ring_count=12, location=p_tip)
        sph = bpy.context.active_object
        segs.append(sph)
        return segs

    # Thumb
    hand_parts.extend(add_finger(
        p_palm + Vector((-0.005, -0.006, 0.024)),
        p_palm + Vector((0.022, -0.015, 0.062)),
        p_palm + Vector((0.050, -0.020, 0.092)),
        0.0165, 0.0140, 0.0120
    ))
    
    # Index
    hand_parts.extend(add_finger(
        p_palm + Vector((0.040, -0.006, 0.024)),
        p_palm + Vector((0.082, -0.014, 0.033)),
        p_palm + Vector((0.124, -0.022, 0.040)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Middle
    hand_parts.extend(add_finger(
        p_palm + Vector((0.044, -0.007, 0.008)),
        p_palm + Vector((0.090, -0.016, 0.010)),
        p_palm + Vector((0.136, -0.026, 0.012)),
        0.0140, 0.0120, 0.0100
    ))
    
    # Ring
    hand_parts.extend(add_finger(
        p_palm + Vector((0.042, -0.008, -0.010)),
        p_palm + Vector((0.084, -0.018, -0.015)),
        p_palm + Vector((0.126, -0.028, -0.018)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Pinky
    hand_parts.extend(add_finger(
        p_palm + Vector((0.036, -0.009, -0.026)),
        p_palm + Vector((0.068, -0.020, -0.038)),
        p_palm + Vector((0.098, -0.030, -0.048)),
        0.0120, 0.0100, 0.0080
    ))
    
    bpy.ops.object.select_all(action='DESELECT')
    for p in hand_parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.join()
    
    arm_obj.data.remesh_voxel_size = 0.0012
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm_obj.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.88
    mod_s.iterations = 26
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    
    return arm_obj

arm_l = build_seamless_caricature_arm()
arm_l.name = "Arm_Left"

# Right Arm (Mirrored along X)
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

# Join Body + Arm_L + Arm_R
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
arm_l.select_set(True)
arm_r.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# --- PART 2: 3D NATURAL BOUNCY AFRO CURLS (540 VISIBLE SPRING RINGLETS ON TOP CROWN) ---
def build_natural_afro_curls(center=Vector((0.0, -0.008, 0.730)), radius_x=0.120, radius_y=0.128, radius_z=0.112, num_curls=540):
    random.seed(99999)
    curl_objects = []
    
    for idx in range(num_curls):
        theta = random.uniform(0.03, 0.44 * math.pi)
        phi = random.uniform(0, 2 * math.pi)
        
        gx = center.x + radius_x * math.sin(theta) * math.cos(phi)
        gy = center.y + radius_y * math.sin(theta) * math.sin(phi)
        gz = center.z + radius_z * math.cos(theta)
        
        # Don't place curls on face or ears
        if gy < -0.015 and gz < 0.775:
            continue
        if abs(gx) > 0.14 and gz < 0.745:
            continue
            
        norm = (Vector((gx, gy, gz)) - center).normalized()
        up = Vector((0, 0, 1))
        if abs(norm.dot(up)) > 0.9:
            up = Vector((0, 1, 0))
        tang = norm.cross(up).normalized()
        bitang = norm.cross(tang).normalized()
        
        turns = random.uniform(3.8, 5.8)
        curl_radius = random.uniform(0.007, 0.013)
        curl_length = random.uniform(0.024, 0.038)
        
        curve_data = bpy.data.curves.new(name=f"PixarCurl_{idx}", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = random.uniform(0.0020, 0.0028)
        curve_data.bevel_resolution = 3
        
        spline = curve_data.splines.new('BEZIER')
        num_pts = 16
        spline.bezier_points.add(num_pts - 1)
        
        phase = random.uniform(0, 2 * math.pi)
        s_start = Vector((gx, gy, gz))
        
        for p in range(num_pts):
            t = p / (num_pts - 1)
            angle = t * turns * 2.0 * math.pi + phase
            
            env = math.sin(t * math.pi * 0.85 + 0.15)
            rad = curl_radius * (0.55 + 0.45 * env)
            
            off_t = math.cos(angle) * rad
            off_b = math.sin(angle) * rad
            off_n = t * curl_length
            
            pos = s_start + tang * off_t + bitang * off_b + norm * off_n
            bp = spline.bezier_points[p]
            bp.co = pos
            bp.handle_left_type = 'AUTO'
            bp.handle_right_type = 'AUTO'
            
        obj = bpy.data.objects.new(f"Curl_{idx}", curve_data)
        bpy.context.scene.collection.objects.link(obj)
        curl_objects.append(obj)
        
    bpy.ops.object.select_all(action='DESELECT')
    for c in curl_objects:
        c.select_set(True)
    bpy.context.view_layer.objects.active = curl_objects[0]
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.join()
    
    hair_mesh = bpy.context.active_object
    hair_mesh.name = "NaturalAfroCurlyHairMesh"
    return hair_mesh

hd_hair_obj = build_natural_afro_curls()

# Join Hair with Body Object
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
hd_hair_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# --- PART 3: PROJECTION CAMERAS FOR T-SHIRT (FRONT & BACK) ---
verts = [body_obj.matrix_world @ v.co for v in body_obj.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn
torso_z = center.z + size.z * 0.08
ortho_s = 0.44

# 1. Torso Front
cam_f = bpy.data.objects.new("CamProjF", bpy.data.cameras.new("CamProjF"))
cam_f.data.type = 'ORTHO'
cam_f.data.ortho_scale = ortho_s
cam_f.location = Vector((center.x, center.y - 2.0, torso_z + 0.02))
cam_f.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_f)

# 2. Torso Back
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

# 1. Material Head (Pristine Warm Golden Caramel Métis Skin 4K with SSS)
mat_head = bpy.data.materials.new(name="Material_Head")
mat_head.use_nodes = True
nh = mat_head.node_tree.nodes
nh.clear()
out_h = nh.new("ShaderNodeOutputMaterial")
bsdf_h = nh.new("ShaderNodeBsdfPrincipled")
tex_h = nh.new("ShaderNodeTexImage")
tex_h.image = bpy.data.images.load(BASE_TEX)
bsdf_h.inputs["Roughness"].default_value = 0.44
if "Subsurface Weight" in bsdf_h.inputs:
    bsdf_h.inputs["Subsurface Weight"].default_value = 0.22
    if "Subsurface Radius" in bsdf_h.inputs:
        bsdf_h.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.25)
elif "Subsurface" in bsdf_h.inputs:
    bsdf_h.inputs["Subsurface"].default_value = 0.22
mat_head.node_tree.links.new(tex_h.outputs["Color"], bsdf_h.inputs["Base Color"])
mat_head.node_tree.links.new(bsdf_h.outputs["BSDF"], out_h.inputs["Surface"])

# 2. Material Hair (Rich Espresso Melanin Curls)
mat_hair = bpy.data.materials.new(name="Material_Hair")
mat_hair.use_nodes = True
nhr = mat_hair.node_tree.nodes
nhr.clear()
out_hr = nhr.new("ShaderNodeOutputMaterial")
bsdf_hr = nhr.new("ShaderNodeBsdfPrincipled")
bsdf_hr.inputs["Base Color"].default_value = (0.012, 0.007, 0.004, 1.0)
bsdf_hr.inputs["Roughness"].default_value = 0.85
if "Specular IOR Level" in bsdf_hr.inputs:
    bsdf_hr.inputs["Specular IOR Level"].default_value = 0.05
elif "Specular" in bsdf_hr.inputs:
    bsdf_hr.inputs["Specular"].default_value = 0.05
mat_hair.node_tree.links.new(bsdf_hr.outputs["BSDF"], out_hr.inputs["Surface"])

# 3. Material Skin Arms (Matching Rich Warm Golden-Caramel Métis with SSS)
mat_skin = bpy.data.materials.new(name="Material_Skin_Arms")
mat_skin.use_nodes = True
ns = mat_skin.node_tree.nodes
ns.clear()
out_s = ns.new("ShaderNodeOutputMaterial")
bsdf_s = ns.new("ShaderNodeBsdfPrincipled")
bsdf_s.inputs["Base Color"].default_value = (0.68, 0.28, 0.12, 1.0)
bsdf_s.inputs["Roughness"].default_value = 0.42
if "Subsurface Weight" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface Weight"].default_value = 0.25
    if "Subsurface Radius" in bsdf_s.inputs:
        bsdf_s.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.25)
elif "Subsurface" in bsdf_s.inputs:
    bsdf_s.inputs["Subsurface"].default_value = 0.25
mat_skin.node_tree.links.new(bsdf_s.outputs["BSDF"], out_s.inputs["Surface"])

# 4. Material Front T-Shirt Graphic 4K (Chest Decal + Seamless Black Base)
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
bsdf_f.inputs["Roughness"].default_value = 0.58
mat_front.node_tree.links.new(uv_f_node.outputs["UV"], tex_f_img.inputs["Vector"])
mat_front.node_tree.links.new(tex_f_img.outputs["Color"], bsdf_f.inputs["Base Color"])
mat_front.node_tree.links.new(bsdf_f.outputs["BSDF"], out_f.inputs["Surface"])

# 5. Material Back T-Shirt Graphic 4K (Back Decal + Seamless Black Base)
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
bsdf_k.inputs["Roughness"].default_value = 0.58
mat_back.node_tree.links.new(uv_k_node.outputs["UV"], tex_k_img.inputs["Vector"])
mat_back.node_tree.links.new(tex_k_img.outputs["Color"], bsdf_k.inputs["Base Color"])
mat_back.node_tree.links.new(bsdf_k.outputs["BSDF"], out_k.inputs["Surface"])

# 6. Material Denim Jeans (Authentic Deep Indigo Denim)
mat_jeans = bpy.data.materials.new(name="Material_Jeans")
mat_jeans.use_nodes = True
nj = mat_jeans.node_tree.nodes
nj.clear()
out_j = nj.new("ShaderNodeOutputMaterial")
bsdf_j = nj.new("ShaderNodeBsdfPrincipled")
bsdf_j.inputs["Base Color"].default_value = (0.016, 0.045, 0.140, 1.0)
bsdf_j.inputs["Roughness"].default_value = 0.72
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

# 8. Material Black T-Shirt Fabric (Shoulders, Collar, Sleeves, Lower Torso & Hem)
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
body_obj.data.materials.append(mat_head)         # 0: Head (Skin)
body_obj.data.materials.append(mat_hair)         # 1: Hair (Curls)
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
        
    # 2. Ears
    if abs(avg_x) > 0.14 and 0.52 < avg_z < 0.74:
        poly.material_index = 0 # Head Skin
        continue
        
    # 3. Face, Eyes, Nose, Lips, Cheeks, Forehead (Smooth skin up to z = 0.815 in front)
    if avg_z > 0.48 and abs(avg_x) <= 0.16 and avg_y < -0.05 and avg_z <= 0.815:
        poly.material_index = 0 # Head Skin
        continue
    elif avg_z > 0.48 and abs(avg_x) <= 0.16 and avg_y < 0.04 and avg_z <= 0.785:
        poly.material_index = 0 # Head Skin
        continue
        
    # 4. Hair (Scalp Crown Dome & 3D Afro Curls)
    if avg_z > 0.815 or (avg_z > 0.785 and avg_y >= -0.05) or (avg_z > 0.65 and avg_y >= 0.04):
        poly.material_index = 1
        continue
        
    # 5. Back of neck below hair
    if avg_z > 0.48 and abs(avg_x) < 0.25:
        poly.material_index = 0 # Head Skin
        continue
        
    # 6. Shoes (Sneakers)
    if avg_z <= -0.72:
        poly.material_index = 6
        continue
        
    # 7. Jeans (From waistline z = -0.18 down to ankles)
    if -0.72 < avg_z <= -0.18:
        poly.material_index = 5
        continue
        
    # 8. Torso / T-Shirt (From collar down to waistline z = -0.18)
    if -0.18 < avg_z <= 0.48:
        # Front chest graphic
        if norm.y < -0.20:
            poly.material_index = 3 # Front Graphic
            continue
        elif norm.y > 0.20:
            poly.material_index = 4 # Back Graphic
            continue
        # Shoulders, collar, sides, hem
        poly.material_index = 7 # Black Shirt Fabric
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
print("SUCCESS_PERFECT_MASTERPIECE_GLB_EXPORTED!")
