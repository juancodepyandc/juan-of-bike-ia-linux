import bpy
import bmesh
import math
from mathutils import Vector, Matrix

REF_IMG_PATH = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_reference.png"
INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
FRONT_DECAL = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
BACK_DECAL = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
OUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/perso_vizion_master_final.glb"

# Step 1: Load 3D mesh into Blender
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

body_obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
bpy.context.view_layer.objects.active = body_obj

# Cut old arm vertices outside sleeve cuff (x > 0.355)
bm = bmesh.new()
bm.from_mesh(body_obj.data)
verts_to_del = [v for v in bm.verts if abs(v.co.x) > 0.355]
bmesh.ops.delete(bm, geom=verts_to_del, context='VERTS')
bm.to_mesh(body_obj.data)
bm.free()
body_obj.data.update()

# Build Flawless Caricature Arms & 5-Finger Hands
def build_flawless_arm_and_hand():
    parts = []
    
    # 1. Forearm: smoothly tapers from sleeve (r=0.048) to wrist (r=0.042)
    p_sleeve = Vector((0.330, 0.035, 0.354))
    p_wrist  = Vector((0.600, -0.015, 0.295))
    p_palm   = Vector((0.640, -0.025, 0.285))
    
    vec_arm = p_wrist - p_sleeve
    len_arm = vec_arm.length
    center_arm = (p_sleeve + p_wrist) * 0.5
    fwd_arm = vec_arm.normalized()
    rot_arm = Vector((0, 0, 1)).rotation_difference(fwd_arm).to_euler()
    
    bpy.ops.mesh.primitive_cone_add(radius1=0.048, radius2=0.042, depth=len_arm, vertices=32, location=center_arm)
    forearm = bpy.context.active_object
    forearm.rotation_euler = rot_arm
    bpy.ops.object.transform_apply(location=True, rotation=True)
    parts.append(forearm)
    
    # 2. Wrist blend sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.043, segments=24, ring_count=16, location=p_wrist)
    wrist_sph = bpy.context.active_object
    wrist_sph.scale = (1.10, 0.70, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(wrist_sph)
    
    # 3. Palm (fleshy, gently cupped forward)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.046, segments=24, ring_count=16, location=p_palm)
    palm = bpy.context.active_object
    palm.scale = (1.20, 0.55, 1.10)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(palm)
    
    # 4. Thenar (thumb base muscle)
    p_thenar = p_palm + Vector((-0.010, 0.012, 0.028))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, segments=20, ring_count=14, location=p_thenar)
    thenar = bpy.context.active_object
    thenar.scale = (1.15, 0.80, 1.05)
    bpy.ops.object.transform_apply(scale=True, location=True)
    parts.append(thenar)
    
    # 5. 5 Expressive Stylized Fingers
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
        # Thumb: curves up (+Z) and forward (-Y)
        ("Thumb",  p_palm + Vector((-0.010, 0.012, 0.030)), p_palm + Vector((0.018, 0.018, 0.070)), p_palm + Vector((0.048, 0.022, 0.098)), 0.0175, 0.0130),
        # Index: elegant
        ("Index",  p_palm + Vector((0.030, 0.002, 0.026)),  p_palm + Vector((0.076, -0.002, 0.036)), p_palm + Vector((0.118, -0.004, 0.044)), 0.0140, 0.0105),
        # Middle: longest finger
        ("Middle", p_palm + Vector((0.034, 0.001, 0.008)),  p_palm + Vector((0.088, -0.003, 0.010)), p_palm + Vector((0.134, -0.005, 0.012)), 0.0145, 0.0110),
        # Ring: natural curvature
        ("Ring",   p_palm + Vector((0.031, 0.000, -0.010)), p_palm + Vector((0.080, -0.004, -0.015)), p_palm + Vector((0.122, -0.006, -0.018)), 0.0140, 0.0105),
        # Pinky: cute, fanned out
        ("Pinky",  p_palm + Vector((0.024, -0.002, -0.026)), p_palm + Vector((0.064, -0.005, -0.040)), p_palm + Vector((0.096, -0.007, -0.050)), 0.0125, 0.0090),
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
    arm.data.remesh_voxel_size = 0.0016
    bpy.ops.object.voxel_remesh()
    
    mod_s = arm.modifiers.new("Smooth", 'SMOOTH')
    mod_s.factor = 0.80
    mod_s.iterations = 18
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.modifier_apply(modifier="Smooth")
    bpy.ops.object.shade_smooth()
    return arm

arm_l = build_flawless_arm_and_hand()
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

# Join Body + Arm_L + Arm_R into 1 single unified object
bpy.ops.object.select_all(action='DESELECT')
body_obj.select_set(True)
arm_l.select_set(True)
arm_r.select_set(True)
bpy.context.view_layer.objects.active = body_obj
bpy.ops.object.join()

# Calculate Full Character Bounds for UV Projection
verts = [body_obj.matrix_world @ v.co for v in body_obj.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn
print(f"Character Size: X={size.x:.3f}, Y={size.y:.3f}, Z={size.z:.3f}, Center={center}")

# Create Front Full-Body Projection Camera
cam_full_f = bpy.data.objects.new("CamFullF", bpy.data.cameras.new("CamFullF"))
cam_full_f.data.type = 'ORTHO'
cam_full_f.data.ortho_scale = size.z * 1.02
cam_full_f.location = Vector((center.x, center.y - 2.0, center.z))
cam_full_f.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_full_f)

# Create Torso Front Decal Projection Camera
cam_decal_f = bpy.data.objects.new("CamDecalF", bpy.data.cameras.new("CamDecalF"))
cam_decal_f.data.type = 'ORTHO'
cam_decal_f.data.ortho_scale = 0.44
torso_z = center.z + size.z * 0.08
cam_decal_f.location = Vector((center.x, center.y - 2.0, torso_z + 0.02))
cam_decal_f.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_decal_f)

# Create Torso Back Decal Projection Camera
cam_decal_b = bpy.data.objects.new("CamDecalB", bpy.data.cameras.new("CamDecalB"))
cam_decal_b.data.type = 'ORTHO'
cam_decal_b.data.ortho_scale = 0.44
cam_decal_b.location = Vector((center.x, center.y + 2.0, torso_z + 0.02))
cam_decal_b.rotation_euler = (math.pi / 2.0, 0, math.pi)
bpy.context.scene.collection.objects.link(cam_decal_b)

# Apply UV projections
uv_front_full = body_obj.data.uv_layers.new(name="UV_Front_Full")
mod_ff = body_obj.modifiers.new("UVProjFullF", 'UV_PROJECT')
mod_ff.uv_layer = "UV_Front_Full"
mod_ff.projector_count = 1
mod_ff.projectors[0].object = cam_full_f
bpy.ops.object.modifier_apply(modifier="UVProjFullF")

uv_front_decal = body_obj.data.uv_layers.new(name="UV_Front_Decal")
mod_fd = body_obj.modifiers.new("UVProjDecalF", 'UV_PROJECT')
mod_fd.uv_layer = "UV_Front_Decal"
mod_fd.projector_count = 1
mod_fd.projectors[0].object = cam_decal_f
bpy.ops.object.modifier_apply(modifier="UVProjDecalF")

uv_back_decal = body_obj.data.uv_layers.new(name="UV_Back_Decal")
mod_bd = body_obj.modifiers.new("UVProjDecalB", 'UV_PROJECT')
mod_bd.uv_layer = "UV_Back_Decal"
mod_bd.projector_count = 1
mod_bd.projectors[0].object = cam_decal_b
bpy.ops.object.modifier_apply(modifier="UVProjDecalB")

# --- MASTER PBR SHADER SETUP ---
mat_master = bpy.data.materials.new(name="Material_Master")
mat_master.use_nodes = True
nodes = mat_master.node_tree.nodes
nodes.clear()
links = mat_master.node_tree.links

out_node = nodes.new("ShaderNodeOutputMaterial")

# Principled BSDF
bsdf = nodes.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Roughness"].default_value = 0.45

# 1. Front Full-Body Texture (Direct from reference image!)
tex_ref = nodes.new("ShaderNodeTexImage")
tex_ref.image = bpy.data.images.load(REF_IMG_PATH)
tex_ref.extension = 'CLIP'

uv_ff_node = nodes.new("ShaderNodeUVMap")
uv_ff_node.uv_map = "UV_Front_Full"
links.new(uv_ff_node.outputs["UV"], tex_ref.inputs["Vector"])

# 2. Front 4K Decal Texture
tex_decal_f = nodes.new("ShaderNodeTexImage")
tex_decal_f.image = bpy.data.images.load(FRONT_DECAL)
tex_decal_f.extension = 'CLIP'
uv_df_node = nodes.new("ShaderNodeUVMap")
uv_df_node.uv_map = "UV_Front_Decal"
links.new(uv_df_node.outputs["UV"], tex_decal_f.inputs["Vector"])

# 3. Back 4K Decal Texture
tex_decal_b = nodes.new("ShaderNodeTexImage")
tex_decal_b.image = bpy.data.images.load(BACK_DECAL)
tex_decal_b.extension = 'CLIP'
uv_db_node = nodes.new("ShaderNodeUVMap")
uv_db_node.uv_map = "UV_Back_Decal"
links.new(uv_db_node.outputs["UV"], tex_decal_b.inputs["Vector"])

# Mix Decal Front
mix_decal_f = nodes.new("ShaderNodeMix")
mix_decal_f.data_type = 'RGBA'
links.new(tex_decal_f.outputs["Alpha"], mix_decal_f.inputs["Factor"])
links.new(tex_ref.outputs["Color"], mix_decal_f.inputs[6]) # A
links.new(tex_decal_f.outputs["Color"], mix_decal_f.inputs[7]) # B

# Mix Decal Back
mix_decal_b = nodes.new("ShaderNodeMix")
mix_decal_b.data_type = 'RGBA'
links.new(tex_decal_b.outputs["Alpha"], mix_decal_b.inputs["Factor"])
links.new(mix_decal_f.outputs[2], mix_decal_b.inputs[6]) # A
links.new(tex_decal_b.outputs["Color"], mix_decal_b.inputs[7]) # B

links.new(mix_decal_b.outputs[2], bsdf.inputs["Base Color"])
links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

body_obj.data.materials.clear()
body_obj.data.materials.append(mat_master)

for c in [cam_full_f, cam_decal_f, cam_decal_b]:
    bpy.data.objects.remove(c, do_unlink=True)

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=False,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_draco_mesh_compression_enable=True
)
print("SUCCESS_MASTER_PROJECTED_GLB_EXPORTED!")
