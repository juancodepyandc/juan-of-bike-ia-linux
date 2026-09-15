import bpy
import bmesh
import math
import numpy as np
from PIL import Image
from mathutils import Vector, Matrix

BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"

# 1. Sample the exact rich golden-amber métis tone from the color-corrected face in texture
im = Image.open(BASE_TEX).convert("RGB")
arr = np.array(im, dtype=np.float32)

# Sample face region in texture (cheeks/nose)
# Face UV center is around U=0.64, V=0.56 -> x around 2620, y around 2300
w, h = im.size
fx, fy = int(0.642 * w), int(0.562 * h)
face_patch = arr[fy-80:fy+80, fx-80:fx+80]
mean_face_rgb = face_patch.mean(axis=(0, 1))
print(f"Sampled Face Golden Métis RGB: {mean_face_rgb}")

# Use the exact face tone for the arm swatches (warm golden amber)
metis_r, metis_g, metis_b = mean_face_rgb[0], mean_face_rgb[1], mean_face_rgb[2]

for cx, cy in [(int(0.3655 * w), int(0.8289 * h)), (int(0.7817 * w), int(0.5153 * h))]:
    arr[cy-250:cy+250, cx-250:cx+250, 0] = metis_r
    arr[cy-250:cy+250, cx-250:cx+250, 1] = metis_g
    arr[cy-250:cy+250, cx-250:cx+250, 2] = metis_b

out_im = Image.fromarray(arr.astype(np.uint8))
out_im.save(BASE_TEX)
print("Harmonized arm swatches with exact face golden métis skin tone!")

# 2. Build Full, Proportional, Expressive 3D Arms & Hands (Matching Reference Caricature)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj

# Cut all old arm vertices outside sleeve cuff (x > 0.355)
bm = bmesh.new()
bm.from_mesh(body_obj.data)
verts_to_del = [v for v in bm.verts if abs(v.co.x) > 0.355]
bmesh.ops.delete(bm, geom=verts_to_del, context='VERTS')
bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

def build_caricature_arm_and_hand():
    parts = []
    
    # Natural welcoming arm pose:
    # Sleeve origin: (0.33, 0.035, 0.354), r=0.050
    # Palm center:   (0.66, -0.015, 0.310), r=0.038 (slight forward Y & downward Z angle)
    p_sleeve = Vector((0.33, 0.035, 0.354))
    p_palm = Vector((0.66, -0.015, 0.310))
    
    vec_arm = p_palm - p_sleeve
    len_arm = vec_arm.length
    center_arm = (p_sleeve + p_palm) * 0.5
    fwd_arm = vec_arm.normalized()
    rot_arm = Vector((0, 0, 1)).rotation_difference(fwd_arm).to_euler()
    
    # Fuller forearm matching stylized caricature anatomy
    bpy.ops.mesh.primitive_cone_add(radius1=0.050, radius2=0.039, depth=len_arm, vertices=32, location=center_arm)
    forearm = bpy.context.active_object
    forearm.rotation_euler = rot_arm
    bpy.ops.object.transform_apply(location=True, rotation=True)
    parts.append(forearm)
    
    # Palm (fleshy, slightly cupped forward)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.048, segments=24, ring_count=16, location=p_palm)
    palm = bpy.context.active_object
    palm.scale = (1.20, 0.56, 1.10)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(palm)
    
    # Thenar (thumb base)
    p_thenar = p_palm + Vector((-0.012, 0.012, 0.030))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.026, segments=20, ring_count=14, location=p_thenar)
    thenar = bpy.context.active_object
    thenar.scale = (1.15, 0.80, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(thenar)
    
    # 5 Expressive Stylized Fingers (Pixar 3D style)
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
        # Thumb: prominent, curves up (+Z) and forward (-Y)
        ("Thumb",  p_palm + Vector((-0.012, 0.012, 0.032)), p_palm + Vector((0.022, 0.022, 0.076)), p_palm + Vector((0.056, 0.026, 0.108)), 0.0180, 0.0135),
        # Index: long, elegant
        ("Index",  p_palm + Vector((0.032, 0.002, 0.028)),  p_palm + Vector((0.084, -0.002, 0.040)), p_palm + Vector((0.132, -0.004, 0.048)), 0.0145, 0.0110),
        # Middle: longest expressive finger
        ("Middle", p_palm + Vector((0.036, 0.001, 0.009)),  p_palm + Vector((0.098, -0.003, 0.012)), p_palm + Vector((0.150, -0.005, 0.014)), 0.0150, 0.0115),
        # Ring: natural curvature
        ("Ring",   p_palm + Vector((0.033, 0.000, -0.010)), p_palm + Vector((0.090, -0.004, -0.016)), p_palm + Vector((0.138, -0.006, -0.020)), 0.0145, 0.0110),
        # Pinky: cute, fanned out
        ("Pinky",  p_palm + Vector((0.026, -0.002, -0.028)), p_palm + Vector((0.072, -0.005, -0.044)), p_palm + Vector((0.110, -0.007, -0.056)), 0.0130, 0.0095),
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
    arm.data.remesh_voxel_size = 0.0020
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.65
    mod_s.iterations = 10
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    
    # Assign UV directly on the arm mesh to clean métis swatch
    bm_arm = bmesh.new()
    bm_arm.from_mesh(arm.data)
    uv_arm = bm_arm.loops.layers.uv.verify()
    target_uv = Vector((0.3655, 0.8289))
    for f in bm_arm.faces:
        for loop in f.loops:
            loop[uv_arm].uv = target_uv
    bm_arm.to_mesh(arm.data)
    bm_arm.free()
    arm.data.update()
    
    return arm

# Left Arm
arm_l = build_caricature_arm_and_hand()
arm_l.name = "Arm_Left"

# Right Arm (mirrored along X)
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

# Both arms have exact same clean swatch UV
bm_r = bmesh.new()
bm_r.from_mesh(arm_r.data)
uv_r = bm_r.loops.layers.uv.verify()
for f in bm_r.faces:
    for loop in f.loops:
        loop[uv_r].uv = Vector((0.3655, 0.8289))
bm_r.to_mesh(arm_r.data)
bm_r.free()
arm_r.data.update()

# Join Body + Arm_L + Arm_R into 1 single unified object
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
arm_l.select_set(True)
arm_r.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# Fix Scalp Apex ONLY (Z > 0.83)
bm = bmesh.new()
bm.from_mesh(body_obj.data)
uv_bm = bm.loops.layers.uv.verify()
for face in bm.faces:
    for loop in face.loops:
        vz = loop.vert.co.z
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
print(f"\nSUCCESS_PERFECT_METIS_ARMS_EXPORTED: {OUT_TEST}\n")
