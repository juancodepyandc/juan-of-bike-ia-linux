#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, math, os, subprocess, sys
from pathlib import Path

BLENDER_SCRIPT = """
import bpy, sys, math
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
input_glb = args[0]
front_img_path = args[1]
back_img_path = args[2]
output_glb = args[3]
tex_size = int(args[4]) if len(args) > 4 else 2048

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=input_glb)

meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not meshes:
    sys.exit(1)

ob = max(meshes, key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active = ob

if not ob.data.uv_layers:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
center = (mn + mx) * 0.5
size = mx - mn
ortho_scale = max(size.x, size.z) * 1.05

# Front Camera
cam_f_data = bpy.data.cameras.new('CamFront')
cam_f_data.type = 'ORTHO'
cam_f_data.ortho_scale = ortho_scale
cam_f = bpy.data.objects.new('CamFront', cam_f_data)
cam_f.location = Vector((center.x, center.y - max(size.y * 3, 5.0), center.z))
cam_f.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
bpy.context.scene.collection.objects.link(cam_f)

# Back Camera
cam_b_data = bpy.data.cameras.new('CamBack')
cam_b_data.type = 'ORTHO'
cam_b_data.ortho_scale = ortho_scale
cam_b = bpy.data.objects.new('CamBack', cam_b_data)
cam_b.location = Vector((center.x, center.y + max(size.y * 3, 5.0), center.z))
cam_b.rotation_euler = (math.pi / 2.0, 0.0, math.pi)
bpy.context.scene.collection.objects.link(cam_b)

baked_tex = bpy.data.images.new('BakedBaseColor', width=tex_size, height=tex_size, alpha=True)
front_img = bpy.data.images.load(front_img_path)
back_img = bpy.data.images.load(back_img_path)

mat = bpy.data.materials.new(name='M_MultiViewPBR')
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

node_out = nodes.new(type='ShaderNodeOutputMaterial')
node_emit = nodes.new(type='ShaderNodeEmission')

# Front mapping
node_tex_f = nodes.new(type='ShaderNodeTexImage')
node_tex_f.image = front_img
node_tex_f.extension = 'EXTEND'

node_coords_f = nodes.new(type='ShaderNodeTexCoord')
node_coords_f.object = cam_f

node_map_f = nodes.new(type='ShaderNodeMapping')
node_map_f.vector_type = 'POINT'
node_map_f.inputs['Location'].default_value = (0.5, 0.5, 0.0)
node_map_f.inputs['Scale'].default_value = (1.0 / ortho_scale, 1.0 / ortho_scale, 1.0)

links.new(node_coords_f.outputs['Object'], node_map_f.inputs['Vector'])
links.new(node_map_f.outputs['Vector'], node_tex_f.inputs['Vector'])

# Back mapping
node_tex_b = nodes.new(type='ShaderNodeTexImage')
node_tex_b.image = back_img
node_tex_b.extension = 'EXTEND'

node_coords_b = nodes.new(type='ShaderNodeTexCoord')
node_coords_b.object = cam_b

node_map_b = nodes.new(type='ShaderNodeMapping')
node_map_b.vector_type = 'POINT'
node_map_b.inputs['Location'].default_value = (0.5, 0.5, 0.0)
node_map_b.inputs['Scale'].default_value = (1.0 / ortho_scale, 1.0 / ortho_scale, 1.0)

links.new(node_coords_b.outputs['Object'], node_map_b.inputs['Vector'])
links.new(node_map_b.outputs['Vector'], node_tex_b.inputs['Vector'])

# Blend front & back according to face normal
node_geom = nodes.new(type='ShaderNodeNewGeometry')
node_dot = nodes.new(type='ShaderNodeVectorMath')
node_dot.operation = 'DOT_PRODUCT'
node_dot.inputs[1].default_value = (0.0, -1.0, 0.0)
links.new(node_geom.outputs['Normal'], node_dot.inputs[0])

node_mix = nodes.new(type='ShaderNodeMix')
node_mix.data_type = 'RGBA'

node_map_range = nodes.new(type='ShaderNodeMapRange')
node_map_range.inputs['From Min'].default_value = -0.2
node_map_range.inputs['From Max'].default_value = 0.2
node_map_range.inputs['To Min'].default_value = 1.0
node_map_range.inputs['To Max'].default_value = 0.0

links.new(node_dot.outputs['Value'], node_map_range.inputs['Value'])
links.new(node_map_range.outputs['Result'], node_mix.inputs['Factor'])
links.new(node_tex_f.outputs['Color'], node_mix.inputs[4])
links.new(node_tex_b.outputs['Color'], node_mix.inputs[5])

links.new(node_mix.outputs[2], node_emit.inputs['Color'])
links.new(node_emit.outputs['Emission'], node_out.inputs['Surface'])

node_target = nodes.new(type='ShaderNodeTexImage')
node_target.image = baked_tex
nodes.active = node_target

ob.data.materials.clear()
ob.data.materials.append(mat)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.margin = 32

bpy.ops.object.bake(type='EMIT')

# Save baked image to PNG disk and pack
tex_png_path = output_glb + '_tex.png'
baked_tex.filepath_raw = tex_png_path
baked_tex.file_format = 'PNG'
baked_tex.save()

# Load saved PNG as packed image for Principled BSDF
final_img = bpy.data.images.load(tex_png_path)
final_img.pack()

nodes.clear()
node_out = nodes.new(type='ShaderNodeOutputMaterial')
node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
node_bsdf.inputs['Roughness'].default_value = 0.45
node_bsdf.inputs['Metallic'].default_value = 0.05

node_final_tex = nodes.new(type='ShaderNodeTexImage')
node_final_tex.image = final_img

links.new(node_final_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])

bpy.ops.export_scene.gltf(
    filepath=output_glb,
    export_format='GLB',
    use_selection=True,
    export_materials='EXPORT',
    export_image_format='AUTO',
    export_attributes=True,
    export_apply=True
)
print('SUCCESS: Front+Back multi-view baked and packed')
"""

def project_multiview(mesh_path: str, front_image: str, back_image: str, output_path: str, tex_size: int = 4096) -> dict:
    blender_path = 'blender'
    for cand in ['/usr/bin/blender', '/usr/local/bin/blender', 'blender']:
        if os.path.isfile(cand) or subprocess.run(['which', cand], capture_output=True).returncode == 0:
            blender_path = cand
            break
            
    tmp_script = Path(output_path).parent / '_tmp_multiview_bake.py'
    tmp_script.write_text(BLENDER_SCRIPT, encoding='utf-8')
    
    cmd = [
        blender_path, '--background', '--python', str(tmp_script),
        '--', str(mesh_path), str(front_image), str(back_image), str(output_path), str(tex_size)
    ]
    
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        tmp_script.unlink(missing_ok=True)
        if Path(output_path).is_file() and proc.returncode == 0:
            return {'ok': True, 'output': str(output_path)}
        else:
            return {'ok': False, 'error': (proc.stderr or proc.stdout)[-500:]}
    except Exception as e:
        tmp_script.unlink(missing_ok=True)
        return {'ok': False, 'error': repr(e)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mesh', required=True)
    parser.add_argument('--front', required=True)
    parser.add_argument('--back', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--res', type=int, default=4096)
    args = parser.parse_args()
    
    res = project_multiview(args.mesh, args.front, args.back, args.output, args.res)
    print(res)
