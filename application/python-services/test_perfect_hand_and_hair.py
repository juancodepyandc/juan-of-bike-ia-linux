import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. Flawless Seamless Arm & Sculpted Welcoming Hand
def build_seamless_open_hand():
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
    
    bpy.ops.mesh.primitive_cone_add(radius1=0.048, radius2=0.038, depth=len_arm, vertices=32, location=center_arm)
    forearm = bpy.context.active_object
    forearm.rotation_euler = rot_arm
    bpy.ops.object.transform_apply(location=True, rotation=True)
    parts.append(forearm)
    
    # Smooth Wrist Capsule (connecting forearm to palm seamlessly)
    p_wrist_mid = (p_wrist + p_palm) * 0.5
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.040, segments=24, ring_count=16, location=p_wrist_mid)
    wrist_mid = bpy.context.active_object
    wrist_mid.scale = (1.10, 0.70, 0.95)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(wrist_mid)
    
    # Palm Body (cupped, angled forward -Y)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.044, segments=24, ring_count=16, location=p_palm)
    palm = bpy.context.active_object
    palm.scale = (1.15, 0.60, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(palm)
    
    # Thenar Eminence (Thumb base muscle pad, prominent on palm side -Y, +Z)
    p_thenar = p_palm + Vector((-0.008, -0.012, 0.024))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.024, segments=20, ring_count=14, location=p_thenar)
    thenar = bpy.context.active_object
    thenar.scale = (1.15, 0.85, 1.10)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(thenar)
    
    # Hypothenar Eminence (Pinky base muscle pad on palm side -Y, -Z)
    p_hypothenar = p_palm + Vector((-0.006, -0.010, -0.020))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.020, segments=18, ring_count=12, location=p_hypothenar)
    hypothenar = bpy.context.active_object
    hypothenar.scale = (1.10, 0.80, 1.00)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(hypothenar)
    
    # 5 Sculpted Fingers (Natural forward curl into welcoming open gesture)
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
            
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r_tip * 1.05, segments=16, ring_count=12, location=p_tip)
        sph = bpy.context.active_object
        segs.append(sph)
        return segs

    # Thumb: curves upward (+Z) and forward (-Y) in clear opposition
    parts.extend(add_finger(
        p_palm + Vector((-0.008, -0.010, 0.026)),
        p_palm + Vector((0.018, -0.018, 0.065)),
        p_palm + Vector((0.046, -0.022, 0.096)),
        0.0170, 0.0145, 0.0125
    ))
    
    # Index: elegant, curved gently forward (-Y)
    parts.extend(add_finger(
        p_palm + Vector((0.030, -0.004, 0.025)),
        p_palm + Vector((0.074, -0.014, 0.035)),
        p_palm + Vector((0.116, -0.024, 0.042)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Middle: longest finger, curved forward (-Y)
    parts.extend(add_finger(
        p_palm + Vector((0.034, -0.005, 0.008)),
        p_palm + Vector((0.084, -0.016, 0.010)),
        p_palm + Vector((0.130, -0.028, 0.012)),
        0.0140, 0.0120, 0.0100
    ))
    
    # Ring: natural curvature forward (-Y)
    parts.extend(add_finger(
        p_palm + Vector((0.031, -0.006, -0.010)),
        p_palm + Vector((0.076, -0.018, -0.015)),
        p_palm + Vector((0.118, -0.030, -0.018)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Pinky: cute, angled outward (-Z) and forward (-Y)
    parts.extend(add_finger(
        p_palm + Vector((0.024, -0.008, -0.026)),
        p_palm + Vector((0.060, -0.020, -0.038)),
        p_palm + Vector((0.092, -0.032, -0.048)),
        0.0120, 0.0100, 0.0080
    ))
    
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = forearm
    bpy.ops.object.join()
    
    arm = bpy.context.active_object
    arm.name = "UnifiedArmAndHand"
    arm.data.remesh_voxel_size = 0.0014
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.85
    mod_s.iterations = 22
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    
    # PBR Material (Warm Golden Caramel Métis with SSS)
    mat_skin = bpy.data.materials.new(name="Material_Skin_Arms")
    mat_skin.use_nodes = True
    bsdf = mat_skin.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.64, 0.26, 0.10, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.42
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.25
        if "Subsurface Radius" in bsdf.inputs:
            bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.25)
    elif "Subsurface" in bsdf.inputs:
        bsdf.inputs["Subsurface"].default_value = 0.25
    arm.data.materials.append(mat_skin)
    
    return arm

arm = build_seamless_open_hand()

# Render Verification of the Hand
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 28
scene.render.resolution_x = 800
scene.render.resolution_y = 800

cam_data = bpy.data.cameras.new("CamHand")
cam = bpy.data.objects.new("CamHand", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# View Hand from front-left (looking directly at palm and fingers)
cam.location = (0.64, -0.42, 0.32)
cam.rotation_euler = (1.45, 0, 0.15)

world = bpy.data.worlds.new("World")
scene.world = world
world.color = (0.04, 0.04, 0.04)

light_data = bpy.data.lights.new(name="KeyLight", type='AREA')
light_data.energy = 80.0
light_data.size = 0.5
light = bpy.data.objects.new(name="KeyLight", object_data=light_data)
scene.collection.objects.link(light)
light.location = (0.50, -0.60, 0.60)

scene.render.filepath = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_hand_palm_view.png"
bpy.ops.render.render(write_still=True)
print("Rendered test_hand_palm_view.png successfully!")
