import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, Euler

bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. Hair Material: Deep Chocolate Espresso with Natural Melanin Hair Sheen
mat_hair = bpy.data.materials.new(name="Material_HD_Afro_Curls")
mat_hair.use_nodes = True
nhr = mat_hair.node_tree.nodes
nhr.clear()
out_hr = nhr.new("ShaderNodeOutputMaterial")
bsdf_hr = nhr.new("ShaderNodeBsdfPrincipled")
# Natural dark chocolate melanin tone
bsdf_hr.inputs["Base Color"].default_value = (0.012, 0.007, 0.004, 1.0)
bsdf_hr.inputs["Roughness"].default_value = 0.52
if "Specular IOR Level" in bsdf_hr.inputs:
    bsdf_hr.inputs["Specular IOR Level"].default_value = 0.18
elif "Specular" in bsdf_hr.inputs:
    bsdf_hr.inputs["Specular"].default_value = 0.18
if "Sheen Weight" in bsdf_hr.inputs:
    bsdf_hr.inputs["Sheen Weight"].default_value = 0.40
elif "Sheen" in bsdf_hr.inputs:
    bsdf_hr.inputs["Sheen"].default_value = 0.40
if "Anisotropic" in bsdf_hr.inputs:
    bsdf_hr.inputs["Anisotropic"].default_value = 0.45
mat_hair.node_tree.links.new(bsdf_hr.outputs["BSDF"], out_hr.inputs["Surface"])

# 2. HD Micro-Curl Generator (1,200 fine curly spiral strands with clump hierarchy)
def build_hd_curly_afro(center=(0.0, -0.012, 0.705), radius_x=0.122, radius_y=0.134, radius_z=0.118, num_clusters=220, strands_per_cluster=6):
    random.seed(1337)
    curl_objects = []
    
    for c_idx in range(num_clusters):
        # Distribute cluster guides over scalp dome
        theta = random.uniform(0.04, 0.46 * math.pi)
        phi = random.uniform(0, 2 * math.pi)
        
        guide_x = center[0] + radius_x * math.sin(theta) * math.cos(phi)
        guide_y = center[1] + radius_y * math.sin(theta) * math.sin(phi)
        guide_z = center[2] + radius_z * math.cos(theta)
        
        # Don't place curls on face or ears
        if guide_y < -0.01 and guide_z < 0.765:
            continue
        if abs(guide_x) > 0.14 and guide_z < 0.74:
            continue
            
        norm = Vector((guide_x - center[0], guide_y - center[1], guide_z - center[2])).normalized()
        up = Vector((0, 0, 1))
        if abs(norm.dot(up)) > 0.9:
            up = Vector((0, 1, 0))
        tang = norm.cross(up).normalized()
        bitang = norm.cross(tang).normalized()
        
        # Cluster parameters
        cluster_turns = random.uniform(3.5, 6.0)
        cluster_rad = random.uniform(0.005, 0.011) # Tight fine coils
        cluster_len = random.uniform(0.022, 0.038)
        
        # Fade factor near hairline
        dist_to_hairline = max(0.0, 0.785 - guide_z) if guide_y < 0.02 else 0.0
        fade_scale = max(0.45, 1.0 - dist_to_hairline * 6.0)
        cluster_rad *= fade_scale
        cluster_len *= fade_scale
        
        for s_idx in range(strands_per_cluster):
            # Minor random offset per child strand in cluster
            strand_angle_offset = (s_idx / strands_per_cluster) * 2.0 * math.pi + random.uniform(-0.3, 0.3)
            strand_radial_offset = random.uniform(0.001, 0.005)
            
            s_start = Vector((guide_x, guide_y, guide_z)) + tang * (math.cos(strand_angle_offset) * strand_radial_offset) + bitang * (math.sin(strand_angle_offset) * strand_radial_offset)
            
            curve_data = bpy.data.curves.new(name=f"HDCurl_{c_idx}_{s_idx}", type='CURVE')
            curve_data.dimensions = '3D'
            # Ultra-fine hair strand bevel (tapered fine strand)
            curve_data.bevel_depth = random.uniform(0.0010, 0.0016) * fade_scale
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
                
                # Tight corkscrew spiral with natural micro-curl coil
                offset_t = math.cos(angle) * strand_rad * (0.6 + 0.6 * math.sin(t * math.pi))
                offset_b = math.sin(angle) * strand_rad * (0.6 + 0.6 * math.sin(t * math.pi))
                offset_n = t * strand_len
                
                pt_pos = s_start + tang * offset_t + bitang * offset_b + norm * offset_n
                bp = spline.bezier_points[p_idx]
                bp.co = pt_pos
                bp.handle_left_type = 'AUTO'
                bp.handle_right_type = 'AUTO'
                
            c_obj = bpy.data.objects.new(f"CurlObj_{c_idx}_{s_idx}", curve_data)
            bpy.context.scene.collection.objects.link(c_obj)
            curl_objects.append(c_obj)
            
    print(f"Generated {len(curl_objects)} fine micro-curl hair strands!")
    
    # Convert all curves to mesh and join into single unified hair mesh
    bpy.ops.object.select_all(action='DESELECT')
    for c in curl_objects:
        c.select_set(True)
    bpy.context.view_layer.objects.active = curl_objects[0]
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.join()
    
    hair_mesh = bpy.context.active_object
    hair_mesh.name = "HDAfroHairMesh"
    hair_mesh.data.materials.append(mat_hair)
    return hair_mesh

hd_hair = build_hd_curly_afro()
print("HD Afro Hair successfully generated!")
