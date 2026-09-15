import bpy
import bmesh
import math
import numpy as np
from mathutils import Vector, Matrix

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

# 1. Clean the skin texture swatch to pure flawless warm caramel skin
img = bpy.data.images.load(BASE_TEX)
w, h = img.size
pixels = np.array(img.pixels[:]).reshape((h, w, 4))

# Left arm skin patch: u around 0.3655, v around 0.8289 -> x around 1400-1600, y around 3300-3500
# Right arm skin patch: u around 0.7817, v around 0.5153 -> x around 3100-3300, y around 2000-2200
# Let's clean the entire skin regions to pure warm caramel skin color
caramel_r = 0.88
caramel_g = 0.45
caramel_b = 0.32

# Fill Left Skin Swatch (radius 120px)
cx_l, cy_l = int(0.3655 * w), int(0.8289 * h)
pixels[cy_l-120:cy_l+120, cx_l-120:cx_l+120, 0] = caramel_r
pixels[cy_l-120:cy_l+120, cx_l-120:cx_l+120, 1] = caramel_g
pixels[cy_l-120:cy_l+120, cx_l-120:cx_l+120, 2] = caramel_b
pixels[cy_l-120:cy_l+120, cx_l-120:cx_l+120, 3] = 1.0

# Fill Right Skin Swatch (radius 120px)
cx_r, cy_r = int(0.7817 * w), int(0.5153 * h)
pixels[cy_r-120:cy_r+120, cx_r-120:cx_r+120, 0] = caramel_r
pixels[cy_r-120:cy_r+120, cx_r-120:cx_r+120, 1] = caramel_g
pixels[cy_r-120:cy_r+120, cx_r-120:cx_r+120, 2] = caramel_b
pixels[cy_r-120:cy_r+120, cx_r-120:cx_r+120, 3] = 1.0

img.pixels = pixels.ravel()
img.filepath_raw = BASE_TEX
img.file_format = 'PNG'
img.save()
print("Flawless skin swatches saved to enhanced_base_texture_4k.png!")

# 2. Build Unified Arm + Hand
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj

sleeve_cut_x = 0.35  # Cut right inside sleeve cuff

# Cut old arms completely from sleeve outwards
bm = bmesh.new()
bm.from_mesh(body_obj.data)
verts_to_del = [v for v in bm.verts if abs(v.co.x) > sleeve_cut_x]
bmesh.ops.delete(bm, geom=verts_to_del, context='VERTS')
bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

def build_complete_arm_and_hand():
    parts = []
    
    # 1. Forearm (starts at x=0.33 inside sleeve, extends to x=0.55 at wrist)
    # Sleeve center: (0.33, 0.037, 0.354), r=0.055
    # Wrist center:  (0.55, -0.002, 0.368), r=0.038
    p_sleeve = Vector((0.33, 0.037, 0.354))
    p_wrist = Vector((0.55, -0.002, 0.368))
    
    vec_arm = p_wrist - p_sleeve
    len_arm = vec_arm.length
    center_arm = (p_sleeve + p_wrist) * 0.5
    fwd_arm = vec_arm.normalized()
    rot_arm = Vector((0, 0, 1)).rotation_difference(fwd_arm).to_euler()
    
    bpy.ops.mesh.primitive_cone_add(radius1=0.054, radius2=0.038, depth=len_arm, vertices=32, location=center_arm)
    forearm = bpy.context.active_object
    forearm.rotation_euler = rot_arm
    bpy.ops.object.transform_apply(location=True, rotation=True)
    parts.append(forearm)
    
    # 2. Palm (centered at p_wrist + (0.045, 0, 0))
    p_palm = p_wrist + Vector((0.045, 0.002, 0.000))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, segments=24, ring_count=16, location=p_palm)
    palm = bpy.context.active_object
    palm.scale = (1.15, 0.50, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(palm)
    
    # 3. Thenar
    p_thenar = p_palm + Vector((-0.015, 0.008, 0.030))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.024, segments=20, ring_count=14, location=p_thenar)
    thenar = bpy.context.active_object
    thenar.scale = (1.1, 0.7, 1.0)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(thenar)
    
    # 4. 5 Fingers (Thumb, Index, Middle, Ring, Pinky)
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
        ("Thumb",  p_palm + Vector((-0.015, 0.008, 0.032)), p_palm + Vector((0.015, 0.016, 0.065)), p_palm + Vector((0.043, 0.020, 0.092)), 0.016, 0.012),
        ("Index",  p_palm + Vector((0.030, 0.000, 0.026)),  p_palm + Vector((0.075, 0.000, 0.036)),  p_palm + Vector((0.115, 0.000, 0.042)),  0.013, 0.0095),
        ("Middle", p_palm + Vector((0.035, 0.000, 0.008)),  p_palm + Vector((0.085, 0.000, 0.010)),  p_palm + Vector((0.130, 0.000, 0.012)),  0.0135, 0.010),
        ("Ring",   p_palm + Vector((0.032, 0.000, -0.010)), p_palm + Vector((0.078, 0.000, -0.016)), p_palm + Vector((0.118, 0.000, -0.020)), 0.013, 0.0095),
        ("Pinky",  p_palm + Vector((0.025, 0.000, -0.028)), p_palm + Vector((0.060, 0.000, -0.040)), p_palm + Vector((0.092, 0.000, -0.048)), 0.0115, 0.008),
    ]
    
    for name, p_root, p_knuckle, p_tip, r_base, r_tip in finger_chains:
        r_mid = (r_base + r_tip) * 0.5
        parts.extend(add_capsule(p_root, p_knuckle, r_base, r_mid))
        parts.extend(add_capsule(p_knuckle, p_tip, r_mid, r_tip))
        
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = forearm
    bpy.ops.object.join()
    
    arm = bpy.context.active_object
    arm.name = "UnifiedArmAndHand"
    # Voxel Remesh to fuse everything into 1 single continuous organic skin sculpt!
    arm.data.remesh_voxel_size = 0.0020
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.60
    mod_s.iterations = 8
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    return arm

# Left Unified Arm
arm_l = build_complete_arm_and_hand()
arm_l.name = "Arm_Left"

# Right Unified Arm (mirrored along X)
bpy.ops.object.select_all(action='DESELECT')
arm_l.select_set(True)
bpy.context.view_layer.objects.active = arm_l
bpy.ops.object.duplicate()
arm_r = bpy.context.active_object
arm_r.name = "Arm_Right"
arm_r.scale = (-1, 1, 1)
bpy.ops.object.transform_apply(scale=True)

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode='OBJECT')

# Join Body + Arm_L + Arm_R into 1 single unified object
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
arm_l.select_set(True)
arm_r.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# Remove doubles inside sleeve hem
bm = bmesh.new()
bm.from_mesh(body_obj.data)
sleeve_verts = [v for v in bm.verts if 0.30 <= abs(v.co.x) <= 0.38]
bmesh.ops.remove_doubles(bm, verts=sleeve_verts, dist=0.005)

# Set 100% flawless UVs for arms and hands
uv_bm = bm.loops.layers.uv.verify()
for face in bm.faces:
    for loop in face.loops:
        vx = loop.vert.co.x
        vz = loop.vert.co.z
        
        # Left Unified Arm and Hand (|x| > 0.30)
        if vx > 0.30:
            loop[uv_bm].uv = Vector((0.3655, 0.8289))
        elif vx < -0.30:
            # Right Unified Arm and Hand
            loop[uv_bm].uv = Vector((0.7817, 0.5153))
            
        # Top Scalp Apex ONLY (Z > 0.83)
        if vz > 0.83:
            uv = loop[uv_bm].uv
            if uv.x < 0.06 or uv.x > 0.60 or uv.y > 0.88 or uv.y < 0.06:
                loop[uv_bm].uv = Vector((0.120, 0.136))

bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

bpy.ops.object.shade_smooth()

OUT_TEST = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_5finger_mesh.glb"
bpy.ops.export_scene.gltf(
    filepath=OUT_TEST,
    export_format='GLB',
    export_apply=True
)
print(f"\nSUCCESS_UNIFIED_ARM_MODEL_EXPORTED: {OUT_TEST}\n")
