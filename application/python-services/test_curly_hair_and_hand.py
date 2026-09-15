import bpy
import bmesh
import math
import random
from mathutils import Vector, Euler, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. Test Helical Curl Generator
def create_curly_afro_dome(center=(0, 0, 0.68), radius_x=0.13, radius_y=0.14, radius_z=0.12, num_curls=160):
    curl_objects = []
    random.seed(42)
    
    # Material for Hair Curls (Deep Chocolate Espresso with Natural Sheen)
    mat_curls = bpy.data.materials.new(name="Material_Afro_Curls")
    mat_curls.use_nodes = True
    bsdf = mat_curls.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.022, 0.014, 0.008, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.40
    elif "Sheen" in bsdf.inputs:
        bsdf.inputs["Sheen"].default_value = 0.40
    if "Anisotropic" in bsdf.inputs:
        bsdf.inputs["Anisotropic"].default_value = 0.30
        
    for i in range(num_curls):
        # Distribute over upper hemisphere (theta: 0 to pi/2, phi: 0 to 2*pi)
        theta = random.uniform(0.05, 0.45 * math.pi)
        phi = random.uniform(0, 2 * math.pi)
        
        # Position on scalp
        scalp_x = center[0] + radius_x * math.sin(theta) * math.cos(phi)
        scalp_y = center[1] + radius_y * math.sin(theta) * math.sin(phi)
        scalp_z = center[2] + radius_z * math.cos(theta)
        
        # Normal pointing outward from center
        norm = Vector((scalp_x - center[0], scalp_y - center[1], scalp_z - center[2])).normalized()
        
        # Generate 3D helical curve
        curve_data = bpy.data.curves.new(name=f"Curl_{i}", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = random.uniform(0.0035, 0.0055)
        curve_data.bevel_resolution = 3
        
        spline = curve_data.splines.new('BEZIER')
        num_points = random.randint(14, 20)
        spline.bezier_points.add(num_points - 1)
        
        # Helical spiral parameters
        turns = random.uniform(2.5, 4.2)
        curl_rad = random.uniform(0.010, 0.016)
        curl_len = random.uniform(0.035, 0.055)
        
        # Build orthogonal basis from normal
        up = Vector((0, 0, 1))
        if abs(norm.dot(up)) > 0.9:
            up = Vector((0, 1, 0))
        tang = norm.cross(up).normalized()
        bitang = norm.cross(tang).normalized()
        
        start_pt = Vector((scalp_x, scalp_y, scalp_z))
        
        for p_idx in range(num_points):
            t = p_idx / (num_points - 1)
            angle = t * turns * 2.0 * math.pi
            
            # Spiral offsets
            offset_t = math.cos(angle) * curl_rad * (0.8 + 0.4 * t)
            offset_b = math.sin(angle) * curl_rad * (0.8 + 0.4 * t)
            offset_n = t * curl_len
            
            pt_pos = start_pt + tang * offset_t + bitang * offset_b + norm * offset_n
            bp = spline.bezier_points[p_idx]
            bp.co = pt_pos
            bp.handle_left_type = 'AUTO'
            bp.handle_right_type = 'AUTO'
            
        curl_obj = bpy.data.objects.new(f"CurlObj_{i}", curve_data)
        bpy.context.scene.collection.objects.link(curl_obj)
        curl_obj.data.materials.append(mat_curls)
        curl_objects.append(curl_obj)
        
    print(f"SUCCESS: Created {len(curl_objects)} 3D curly afro ringlets!")
    return curl_objects

curls = create_curly_afro_dome()
print("Test completed successfully!")
