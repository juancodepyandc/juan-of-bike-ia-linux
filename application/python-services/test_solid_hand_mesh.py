import bpy
import bmesh
import math
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)

def build_solid_caricature_arm():
    bm = bmesh.new()
    
    # Centerline profile of the arm from sleeve cuff to the knuckle pads
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
            
    # Cap sleeve end
    bm.faces.new(rings[0][::-1])
    
    # Cap palm end with a convex rounded tip
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

    # Thumb: curves upward (+Z) and forward (-Y) in clear opposition
    hand_parts.extend(add_finger(
        p_palm + Vector((-0.005, -0.006, 0.024)),
        p_palm + Vector((0.022, -0.015, 0.062)),
        p_palm + Vector((0.050, -0.020, 0.092)),
        0.0165, 0.0140, 0.0120
    ))
    
    # Index: elegant, curved forward (-Y)
    hand_parts.extend(add_finger(
        p_palm + Vector((0.040, -0.006, 0.024)),
        p_palm + Vector((0.082, -0.014, 0.033)),
        p_palm + Vector((0.124, -0.022, 0.040)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Middle: longest finger, curved forward (-Y)
    hand_parts.extend(add_finger(
        p_palm + Vector((0.044, -0.007, 0.008)),
        p_palm + Vector((0.090, -0.016, 0.010)),
        p_palm + Vector((0.136, -0.026, 0.012)),
        0.0140, 0.0120, 0.0100
    ))
    
    # Ring: natural curvature forward (-Y)
    hand_parts.extend(add_finger(
        p_palm + Vector((0.042, -0.008, -0.010)),
        p_palm + Vector((0.084, -0.018, -0.015)),
        p_palm + Vector((0.126, -0.028, -0.018)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Pinky: cute, angled outward (-Z) and forward (-Y)
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
    
    # Voxel Remesh + Smooth for 100% watertight continuous organic mesh
    arm_obj.data.remesh_voxel_size = 0.0012
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm_obj.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.88
    mod_s.iterations = 26
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    
    mat_skin = bpy.data.materials.new(name="Material_Skin_Arms")
    mat_skin.use_nodes = True
    bsdf = mat_skin.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.64, 0.26, 0.10, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.42
    arm_obj.data.materials.append(mat_skin)
    
    return arm_obj

arm = build_solid_caricature_arm()

# Render Verification
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

scene.render.filepath = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_solid_hand_view.png"
bpy.ops.render.render(write_still=True)
print("Rendered test_solid_hand_view.png successfully!")
