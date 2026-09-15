import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Euler

bpy.ops.wm.read_factory_settings(use_empty=True)

def build_loft_hand():
    # Construct a continuous BMesh loft from sleeve to palm to fingertips
    bm = bmesh.new()
    
    # 1. Arm centerline points and radii (smooth organic tapering)
    profile = [
        # (center_vector, radius_z, radius_y)
        (Vector((0.330,  0.035, 0.354)), 0.048, 0.046), # Sleeve Cuff
        (Vector((0.420,  0.018, 0.334)), 0.045, 0.043), # Upper Forearm
        (Vector((0.510,  0.002, 0.314)), 0.041, 0.038), # Mid Forearm
        (Vector((0.580, -0.010, 0.298)), 0.036, 0.030), # Pre-wrist
        (Vector((0.615, -0.016, 0.290)), 0.034, 0.026), # Wrist joint
        (Vector((0.645, -0.022, 0.282)), 0.040, 0.024), # Palm center
        (Vector((0.675, -0.028, 0.274)), 0.044, 0.022), # Knuckles line
    ]
    
    rings = []
    num_sides = 24
    for i, (center, rz, ry) in enumerate(profile):
        ring_verts = []
        # Calculate local forward direction
        if i < len(profile) - 1:
            fwd = (profile[i+1][0] - center).normalized()
        else:
            fwd = (center - profile[i-1][0]).normalized()
            
        up = Vector((0, 0, 1))
        tang_z = (up - fwd * fwd.dot(up)).normalized()
        tang_y = fwd.cross(tang_z).normalized()
        
        for s in range(num_sides):
            angle = (s / num_sides) * 2.0 * math.pi
            # Construct oval cross-section
            offset = tang_z * (math.cos(angle) * rz) + tang_y * (math.sin(angle) * ry)
            v = bm.verts.new(center + offset)
            ring_verts.append(v)
        rings.append(ring_verts)
        
    # Bridge rings into single seamless quad tube
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
            
    # Cap the sleeve end (inside shirt)
    bm.faces.new(rings[0][::-1])
    
    # Close palm distal end (cap before fingers)
    bm.faces.new(rings[-1])
    
    mesh = bpy.data.meshes.new("LoftArmMesh")
    bm.to_mesh(mesh)
    bm.free()
    
    arm_obj = bpy.data.objects.new("LoftArm", mesh)
    bpy.context.scene.collection.objects.link(arm_obj)
    
    # 2. Add Sculpted 5 Fingers
    fingers = []
    p_palm = Vector((0.645, -0.022, 0.282))
    
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

    # Thumb: curves upward (+Z) and forward (-Y)
    fingers.extend(add_finger(
        p_palm + Vector((-0.005, -0.006, 0.024)),
        p_palm + Vector((0.022, -0.015, 0.062)),
        p_palm + Vector((0.050, -0.020, 0.092)),
        0.0165, 0.0140, 0.0120
    ))
    
    # Index: elegant, curved forward (-Y)
    fingers.extend(add_finger(
        p_palm + Vector((0.030, -0.003, 0.024)),
        p_palm + Vector((0.074, -0.012, 0.033)),
        p_palm + Vector((0.116, -0.022, 0.040)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Middle: longest finger, curved forward (-Y)
    fingers.extend(add_finger(
        p_palm + Vector((0.034, -0.004, 0.008)),
        p_palm + Vector((0.084, -0.014, 0.010)),
        p_palm + Vector((0.130, -0.026, 0.012)),
        0.0140, 0.0120, 0.0100
    ))
    
    # Ring: natural curvature forward (-Y)
    fingers.extend(add_finger(
        p_palm + Vector((0.031, -0.005, -0.010)),
        p_palm + Vector((0.076, -0.016, -0.015)),
        p_palm + Vector((0.118, -0.028, -0.018)),
        0.0135, 0.0115, 0.0095
    ))
    
    # Pinky: cute, angled outward (-Z) and forward (-Y)
    fingers.extend(add_finger(
        p_palm + Vector((0.024, -0.007, -0.026)),
        p_palm + Vector((0.060, -0.018, -0.038)),
        p_palm + Vector((0.092, -0.030, -0.048)),
        0.0120, 0.0100, 0.0080
    ))
    
    # Join arm and fingers into single watertight mesh
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select_set(True)
    for f in fingers:
        f.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.join()
    
    # Voxel Remesh + Smooth
    arm_obj.data.remesh_voxel_size = 0.0012
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm_obj.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.85
    mod_s.iterations = 24
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    
    # Material
    mat_skin = bpy.data.materials.new(name="Material_Skin_Arms")
    mat_skin.use_nodes = True
    bsdf = mat_skin.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.64, 0.26, 0.10, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.42
    arm_obj.data.materials.append(mat_skin)
    
    return arm_obj

arm = build_loft_hand()

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

scene.render.filepath = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_hand_loft_view.png"
bpy.ops.render.render(write_still=True)
print("Rendered test_hand_loft_view.png successfully!")
