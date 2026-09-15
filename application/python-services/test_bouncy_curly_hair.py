import bpy
import bmesh
import math
import random
from mathutils import Vector, Euler, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)

# Test curly hair generator on a head dome
def generate_bouncy_afro_curls(center=Vector((0.0, -0.012, 0.705)), radius_x=0.122, radius_y=0.134, radius_z=0.118, num_curls=380):
    random.seed(42)
    curl_objects = []
    
    for idx in range(num_curls):
        theta = random.uniform(0.03, 0.48 * math.pi)
        phi = random.uniform(0, 2 * math.pi)
        
        gx = center.x + radius_x * math.sin(theta) * math.cos(phi)
        gy = center.y + radius_y * math.sin(theta) * math.sin(phi)
        gz = center.z + radius_z * math.cos(theta)
        
        # Don't place curls on face or ears
        if gy < -0.015 and gz < 0.765:
            continue
        if abs(gx) > 0.14 and gz < 0.74:
            continue
            
        norm = (Vector((gx, gy, gz)) - center).normalized()
        up = Vector((0, 0, 1))
        if abs(norm.dot(up)) > 0.9:
            up = Vector((0, 1, 0))
        tang = norm.cross(up).normalized()
        bitang = norm.cross(tang).normalized()
        
        # Hairline curls hang forward slightly
        is_front = (gy < 0.02 and gz < 0.785)
        turns = random.uniform(4.5, 7.5)
        curl_radius = random.uniform(0.007, 0.015)
        curl_length = random.uniform(0.028, 0.048)
        
        if is_front:
            curl_length *= 0.85
            curl_radius *= 0.90
            norm = (norm + Vector((0, -0.4, -0.3))).normalized()
            
        curve_data = bpy.data.curves.new(name=f"BouncyCurl_{idx}", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = random.uniform(0.0016, 0.0024)
        curve_data.bevel_resolution = 3
        
        spline = curve_data.splines.new('BEZIER')
        num_pts = 18
        spline.bezier_points.add(num_pts - 1)
        
        phase = random.uniform(0, 2 * math.pi)
        s_start = Vector((gx, gy, gz))
        
        for p in range(num_pts):
            t = p / (num_pts - 1)
            angle = t * turns * 2.0 * math.pi + phase
            
            # Envelope for coil radius: bulbous in middle, tapered at tip
            env = math.sin(t * math.pi * 0.85 + 0.15)
            rad = curl_radius * (0.5 + 0.5 * env)
            
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
    hair_mesh.name = "BouncyCurlyHairMesh"
    print(f"Generated curly hair with {len(hair_mesh.data.polygons)} polygons!")
    return hair_mesh

generate_bouncy_afro_curls()
