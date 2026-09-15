import bpy
import math
from mathutils import Vector, Quaternion

bpy.ops.wm.read_factory_settings(use_empty=True)

parts = []

# Palm
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, segments=24, ring_count=16, location=(0.040, 0, 0))
palm = bpy.context.active_object
palm.scale = (1.15, 0.45, 1.05)
bpy.ops.object.transform_apply(scale=True)
parts.append(palm)

# Thenar
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.024, segments=20, ring_count=14, location=(0.025, 0.008, 0.030))
thenar = bpy.context.active_object
thenar.scale = (1.1, 0.7, 1.0)
bpy.ops.object.transform_apply(scale=True)
parts.append(thenar)

# Wrist
bpy.ops.mesh.primitive_cylinder_add(radius=0.026, depth=0.065, vertices=24, location=(-0.015, 0, 0))
wrist = bpy.context.active_object
wrist.rotation_euler = (0, math.radians(90), 0)
bpy.ops.object.transform_apply(rotation=True)
parts.append(wrist)

def add_capsule(p_start, p_end, r_start, r_end):
    vec = p_end - p_start
    length = vec.length
    center = (p_start + p_end) * 0.5
    fwd = vec.normalized()
    rot = Vector((0, 0, 1)).rotation_difference(fwd).to_euler()
    
    bpy.ops.mesh.primitive_cone_add(radius1=r_start, radius2=r_end, depth=length, vertices=16, location=center)
    cone = bpy.context.active_object
    cone.rotation_euler = rot
    bpy.ops.object.transform_apply(location=True, rotation=True)
    
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r_end*1.02, segments=16, ring_count=12, location=p_end)
    sph = bpy.context.active_object
    return [cone, sph]

# 5 Fingers with explicit 3D positions!
# Root -> Knuckle -> Tip
# Thumb points UP (+Z) and OUTWARD (+X) and slightly FRONT (+Y)
# 4 Fingers point OUTWARD (+X) fanned along Z
finger_chains = [
    # (name, root, knuckle, tip, r_base, r_tip)
    ("Thumb",  Vector((0.025, 0.008, 0.032)), Vector((0.055, 0.018, 0.065)), Vector((0.080, 0.022, 0.090)), 0.016, 0.012),
    ("Index",  Vector((0.070, 0.000, 0.026)), Vector((0.115, 0.000, 0.036)), Vector((0.155, 0.000, 0.042)), 0.013, 0.0095),
    ("Middle", Vector((0.075, 0.000, 0.008)), Vector((0.125, 0.000, 0.010)), Vector((0.170, 0.000, 0.012)), 0.0135, 0.010),
    ("Ring",   Vector((0.072, 0.000, -0.010)), Vector((0.118, 0.000, -0.016)), Vector((0.158, 0.000, -0.020)), 0.013, 0.0095),
    ("Pinky",  Vector((0.065, 0.000, -0.028)), Vector((0.100, 0.000, -0.040)), Vector((0.132, 0.000, -0.048)), 0.0115, 0.008),
]

for name, p_root, p_knuckle, p_tip, r_base, r_tip in finger_chains:
    r_mid = (r_base + r_tip) * 0.5
    parts.extend(add_capsule(p_root, p_knuckle, r_base, r_mid))
    parts.extend(add_capsule(p_knuckle, p_tip, r_mid, r_tip))

bpy.ops.object.select_all(action='DESELECT')
for p in parts:
    p.select_set(True)
bpy.context.view_layer.objects.active = palm
bpy.ops.object.join()

hand = bpy.context.active_object
hand.data.remesh_voxel_size = 0.0022
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
cam.location = (0.09, -0.45, 0.02)
cam.rotation_euler = (math.radians(90), 0, 0)

light = bpy.data.objects.new("Light", bpy.data.lights.new("Light", type='AREA'))
light.data.energy = 80
light.location = (0.12, -0.3, 0.25)
bpy.context.scene.collection.objects.link(light)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 32
bpy.context.scene.render.resolution_x = 768
bpy.context.scene.render.resolution_y = 768
bpy.context.scene.render.filepath = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/verifications/test_perfect_vector_hand.png"
bpy.ops.render.render(write_still=True)
print("Rendered perfect vector hand preview!")
