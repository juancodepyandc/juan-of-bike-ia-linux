import bpy
import bmesh
import math
from mathutils import Vector, Matrix

def create_pixar_caricature_hand():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    parts = []
    
    # 1. Main Palm: Organic oval block
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.038, segments=24, ring_count=16, location=(0.035, 0, 0))
    palm = bpy.context.active_object
    palm.scale = (1.10, 0.45, 1.00)
    bpy.ops.object.transform_apply(scale=True)
    parts.append(palm)
    
    # Thenar (thumb muscle base)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.020, segments=20, ring_count=14, location=(0.022, 0.008, 0.025))
    thenar = bpy.context.active_object
    thenar.scale = (1.1, 0.7, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    parts.append(thenar)
    
    # Wrist connector
    bpy.ops.mesh.primitive_cylinder_add(radius=0.026, depth=0.060, vertices=24, location=(-0.015, 0, 0))
    wrist = bpy.context.active_object
    wrist.rotation_euler = (0, math.radians(90), 0)
    bpy.ops.object.transform_apply(rotation=True)
    parts.append(wrist)
    
    # 5 Fingers: (name, z_root, y_root, x_root, flen, r_base, r_tip, spread_angle_z, fwd_angle_y)
    fingers_data = [
        ("Thumb",   0.030,  0.012, 0.025, 0.065, 0.0145, 0.0115,  50,  28),
        ("Index",   0.026,  0.000, 0.065, 0.082, 0.0122, 0.0092,  15,   0),
        ("Middle",  0.009,  0.000, 0.070, 0.092, 0.0126, 0.0095,   3,   0),
        ("Ring",   -0.009,  0.000, 0.068, 0.082, 0.0120, 0.0090,  -9,   0),
        ("Pinky",  -0.026,  0.000, 0.062, 0.066, 0.0108, 0.0078, -24,   0),
    ]
    
    for name, pz, py, px, flen, r_base, r_tip, rz_deg, ry_deg in fingers_data:
        seg1_len = flen * 0.52
        seg2_len = flen * 0.48
        rot_m = Matrix.Rotation(math.radians(rz_deg), 4, 'Z') @ Matrix.Rotation(math.radians(90) + math.radians(ry_deg), 4, 'Y')
        fwd_dir = rot_m @ Vector((0, 0, 1))
        
        root_pt = Vector((px, py, pz))
        
        # Segment 1
        s1_pos = root_pt + fwd_dir * (seg1_len * 0.5)
        bpy.ops.mesh.primitive_cone_add(radius1=r_base, radius2=(r_base+r_tip)*0.5, depth=seg1_len, vertices=16, location=s1_pos)
        s1 = bpy.context.active_object
        s1.rotation_euler = (0, math.radians(90) + math.radians(ry_deg), math.radians(rz_deg))
        bpy.ops.object.transform_apply(location=True, rotation=True)
        
        # Knuckle joint
        k_pos = root_pt + fwd_dir * seg1_len
        bpy.ops.mesh.primitive_uv_sphere_add(radius=(r_base+r_tip)*0.52, segments=16, ring_count=12, location=k_pos)
        k_sph = bpy.context.active_object
        
        # Segment 2
        s2_pos = k_pos + fwd_dir * (seg2_len * 0.5)
        bpy.ops.mesh.primitive_cone_add(radius1=(r_base+r_tip)*0.5, radius2=r_tip, depth=seg2_len, vertices=16, location=s2_pos)
        s2 = bpy.context.active_object
        s2.rotation_euler = (0, math.radians(90) + math.radians(ry_deg), math.radians(rz_deg))
        bpy.ops.object.transform_apply(location=True, rotation=True)
        
        # Fingertip sphere
        tip_pos = k_pos + fwd_dir * seg2_len
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r_tip*1.02, segments=16, ring_count=12, location=tip_pos)
        t_sph = bpy.context.active_object
        
        parts.extend([s1, k_sph, s2, t_sph])
        
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = palm
    bpy.ops.object.join()
    
    hand = bpy.context.active_object
    hand.name = "StylizedCaricatureHand"
    
    # Remesh
    hand.data.remesh_voxel_size = 0.0020
    bpy.ops.object.voxel_remesh()
    
    mod_s = hand.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.60
    mod_s.iterations = 6
    bpy.ops.object.modifier_apply(modifier="Smooth")
    
    bpy.ops.object.shade_smooth()
    
    # Verification render
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.location = (0.06, -0.42, 0.01)
    cam.rotation_euler = (math.radians(90), 0, 0)
    
    light = bpy.data.objects.new("Light", bpy.data.lights.new("Light", type='AREA'))
    light.data.energy = 80
    light.location = (0.12, -0.3, 0.25)
    bpy.context.scene.collection.objects.link(light)
    
    mat = bpy.data.materials.new(name="Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.78, 0.46, 0.30, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.45
    hand.data.materials.append(mat)
    
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.cycles.samples = 32
    bpy.context.scene.render.resolution_x = 768
    bpy.context.scene.render.resolution_y = 768
    bpy.context.scene.render.filepath = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_pixar_hand_preview.png"
    bpy.ops.render.render(write_still=True)
    print("Rendered perfected Pixar-style caricature hand preview!")
    return hand

create_pixar_caricature_hand()
