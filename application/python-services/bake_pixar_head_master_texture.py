import bpy
import math
from mathutils import Vector

INPUT_GLB = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
HEAD_REF = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/head_crop_ref.png"
OUT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/pixar_projected_head_4k.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=INPUT_GLB)

obj = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))

# Setup head projection camera exactly focused on the face
cam_head = bpy.data.objects.new("CamHeadProj", bpy.data.cameras.new("CamHeadProj"))
cam_head.data.type = 'ORTHO'
cam_head.data.ortho_scale = 0.46
cam_head.location = Vector((0.0, -1.5, 0.62))
cam_head.rotation_euler = (math.pi / 2.0, 0, 0)
bpy.context.scene.collection.objects.link(cam_head)

uv_head = obj.data.uv_layers.new(name="UV_Head_Proj")
mod_hp = obj.modifiers.new("UVProjHead", 'UV_PROJECT')
mod_hp.uv_layer = "UV_Head_Proj"
mod_hp.projector_count = 1
mod_hp.projectors[0].object = cam_head
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier="UVProjHead")

print("SUCCESS_UV_HEAD_PROJECTED!")
