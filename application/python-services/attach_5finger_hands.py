import bpy
import bmesh
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
OUTPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj

verts = [body_obj.matrix_world @ v.co for v in body_obj.data.vertices]
arm_verts_l = [v for v in verts if v.x > 0.50]
wrist_l_z = sum(v.z for v in arm_verts_l) / len(arm_verts_l)
wrist_l_y = sum(v.y for v in arm_verts_l) / len(arm_verts_l)
wrist_cut_x = 0.58

# 1. Cut old hands cleanly at wrist
bm = bmesh.new()
bm.from_mesh(body_obj.data)
verts_to_del = [v for v in bm.verts if abs(v.co.x) > wrist_cut_x]
bmesh.ops.delete(bm, geom=verts_to_del, context='VERTS')
bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

# 2. Build High-Quality 5-Finger Hand
def build_hand():
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
    
    # Forearm connector
    bpy.ops.mesh.primitive_cone_add(radius1=0.030, radius2=0.025, depth=0.075, vertices=24, location=(-0.020, 0, 0))
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
        
    finger_chains = [
        ("Thumb",  Vector((0.025, 0.008, 0.032)), Vector((0.055, 0.016, 0.065)), Vector((0.082, 0.020, 0.092)), 0.016, 0.012),
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
    hand.name = "StylizedCaricatureHand"
    hand.data.remesh_voxel_size = 0.0022
    bpy.ops.object.voxel_remesh()
    
    mod_s = hand.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.60
    mod_s.iterations = 6
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    return hand

# Left Hand
hand_l = build_hand()
hand_l.name = "Hand_Left"
hand_l.location = (wrist_cut_x - 0.015, wrist_l_y, wrist_l_z - 0.015)
bpy.ops.object.transform_apply(location=True)

# Right Hand
bpy.ops.object.select_all(action='DESELECT')
hand_l.select_set(True)
bpy.context.view_layer.objects.active = hand_l
bpy.ops.object.duplicate()
hand_r = bpy.context.active_object
hand_r.name = "Hand_Right"
hand_r.scale = (-1, 1, 1)
bpy.ops.object.transform_apply(scale=True)

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode='OBJECT')

# Join body + Left Hand + Right Hand
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
hand_l.select_set(True)
hand_r.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

final_obj = bpy.context.active_object

# UV Mapping
mesh = final_obj.data
bm = bmesh.new()
bm.from_mesh(mesh)
uv_bm = bm.loops.layers.uv.verify()

for face in bm.faces:
    for loop in face.loops:
        vx = loop.vert.co.x
        vz = loop.vert.co.z
        
        # Hands UVs
        if vx > 0.52:
            loop[uv_bm].uv = Vector((0.3655, 0.8289))
        elif vx < -0.52:
            loop[uv_bm].uv = Vector((0.7817, 0.5153))
            
        # Top Scalp Apex ONLY (Z > 0.83)
        if vz > 0.83:
            uv = loop[uv_bm].uv
            # If UV is near borders/margins
            if uv.x < 0.06 or uv.x > 0.60 or uv.y > 0.88 or uv.y < 0.06:
                loop[uv_bm].uv = Vector((0.120, 0.136))

bm.to_mesh(mesh)
bm.free()
mesh.update()

bpy.ops.export_scene.gltf(
    filepath=OUTPUT_GLB,
    export_format='GLB',
    export_apply=True
)
print("SUCCESS_5FINGER_ATTACHED!")
