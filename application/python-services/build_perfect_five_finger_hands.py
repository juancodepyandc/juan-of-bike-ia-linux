import bpy
import math
from mathutils import Vector, Matrix

def create_hand_mesh(is_right=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    parts = []
    
    # 1. Palm (rounded box)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    palm = bpy.context.active_object
    palm.scale = (0.065, 0.028, 0.070)
    bpy.ops.object.transform_apply(scale=True)
    parts.append(palm)
    
    # 2. 5 Fingers: Thumb + 4 fingers
    # (name, x_pos, y_pos, z_pos, length, rad, rot_y_deg, rot_x_deg)
    fingers = [
        ("Thumb",  -0.038,  0.010, -0.010, 0.055, 0.014, -50,  25),
        ("Index",  -0.024,  0.000,  0.065, 0.068, 0.0125, -6,   0),
        ("Middle",  0.000,  0.000,  0.072, 0.075, 0.0130,  0,   0),
        ("Ring",    0.022,  0.000,  0.066, 0.070, 0.0120,  6,   0),
        ("Pinky",   0.040,  0.000,  0.052, 0.056, 0.0105, 14,   0),
    ]
    
    for name, px, py, pz, flen, frad, ry, rx in fingers:
        # Create cylinder with rounded caps
        bpy.ops.mesh.primitive_cylinder_add(
            radius=frad, 
            depth=flen, 
            vertices=16, 
            location=(px, py, pz)
        )
        f_obj = bpy.context.active_object
        f_obj.rotation_euler = (math.radians(rx), math.radians(ry), 0)
        bpy.ops.object.transform_apply(location=True, rotation=True)
        
        # Add fingertip sphere
        tip_dir = Matrix.Rotation(math.radians(ry), 4, 'Y') @ Matrix.Rotation(math.radians(rx), 4, 'X') @ Vector((0, 0, flen*0.5))
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=frad*0.95, 
            segments=16, 
            ring_count=12, 
            location=(px + tip_dir.x, py + tip_dir.y, pz + tip_dir.z)
        )
        s_obj = bpy.context.active_object
        parts.extend([f_obj, s_obj])
        
    # Join all parts
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = palm
    bpy.ops.object.join()
    
    hand_obj = bpy.context.active_object
    hand_obj.name = "FiveFingerHand"
    
    # Voxel Remesh to fuse into organic, seamless single mesh!
    hand_obj.data.remesh_voxel_size = 0.004
    bpy.ops.object.voxel_remesh()
    
    # Smooth modifier
    mod_s = hand_obj.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.65
    mod_s.iterations = 8
    bpy.ops.object.modifier_apply(modifier="Smooth")
    
    bpy.ops.object.shade_smooth()
    
    print(f"Constructed seamless 5-finger hand: {len(hand_obj.data.vertices)} vertices, {len(hand_obj.data.polygons)} polygons.")
    return hand_obj

hand = create_hand_mesh()
# Lighting & Camera for verification render
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.location = (0, -0.45, 0.05)
cam.rotation_euler = (math.radians(90), 0, 0)

light = bpy.data.objects.new("Light", bpy.data.lights.new("Light", type='AREA'))
light.data.energy = 80
light.location = (0.2, -0.3, 0.3)
bpy.context.scene.collection.objects.link(light)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 32
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.context.scene.render.filepath = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_5finger_hand_preview.png"
bpy.ops.render.render(write_still=True)
print("Rendered 5-finger hand preview!")
