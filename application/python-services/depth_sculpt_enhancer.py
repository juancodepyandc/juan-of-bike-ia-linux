#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, math, os, subprocess, sys
from pathlib import Path

BLENDER_DEPTH_SCRIPT = """
import bpy, sys, math
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
input_glb = args[0]
output_glb = args[1]
target_depth_ratio = float(args[2]) if len(args) > 2 else 0.55

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=input_glb)

meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not meshes:
    sys.exit(1)

ob = max(meshes, key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active = ob

verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
mn = Vector(map(min, *verts))
mx = Vector(map(max, *verts))
size = mx - mn

# Detect depth axis (the thinnest axis among X, Y, Z)
axes = [(size.x, 'x', 0), (size.y, 'y', 1), (size.z, 'z', 2)]
axes.sort(key=lambda a: a[0])
min_dim, min_axis_name, min_axis_idx = axes[0]
max_dim = max(size.x, size.y, size.z)

current_ratio = min_dim / max_dim
print(f'Detected min axis: {min_axis_name} ({min_dim:.3f}), max dim: {max_dim:.3f}, ratio: {current_ratio:.3f}')

if current_ratio < target_depth_ratio:
    scale_factor = target_depth_ratio / max(current_ratio, 0.05)
    # Clamp scale factor to reasonable limit [1.5, 3.5]
    scale_factor = min(max(scale_factor, 1.0), 3.5)
    print(f'Applying depth volume scale factor: {scale_factor:.2f} on axis {min_axis_name}')
    
    # Scale along depth axis around object center
    center = (mn + mx) * 0.5
    for v in ob.data.vertices:
        co = v.co
        if min_axis_idx == 0:
            v.co.x = center.x + (co.x - center.x) * scale_factor
        elif min_axis_idx == 1:
            v.co.y = center.y + (co.y - center.y) * scale_factor
        elif min_axis_idx == 2:
            v.co.z = center.z + (co.z - center.z) * scale_factor
            
    ob.data.update()

bpy.ops.export_scene.gltf(
    filepath=output_glb,
    export_format='GLB',
    use_selection=True,
    export_materials='EXPORT',
    export_image_format='AUTO',
    export_attributes=True,
    export_apply=True
)
print('SUCCESS: Depth sculpted and exported')
"""

def enhance_depth(input_glb: str, output_glb: str, target_ratio: float = 0.55) -> dict:
    blender_path = 'blender'
    for cand in ['/usr/bin/blender', '/usr/local/bin/blender', 'blender']:
        if os.path.isfile(cand) or subprocess.run(['which', cand], capture_output=True).returncode == 0:
            blender_path = cand
            break
            
    tmp_script = Path(output_glb).parent / '_tmp_depth_script.py'
    tmp_script.write_text(BLENDER_DEPTH_SCRIPT, encoding='utf-8')
    
    cmd = [
        blender_path, '--background', '--python', str(tmp_script),
        '--', str(input_glb), str(output_glb), str(target_ratio)
    ]
    
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        tmp_script.unlink(missing_ok=True)
        if Path(output_glb).is_file() and proc.returncode == 0:
            return {'ok': True, 'output': str(output_glb)}
        else:
            return {'ok': False, 'error': (proc.stderr or proc.stdout)[-500:]}
    except Exception as e:
        tmp_script.unlink(missing_ok=True)
        return {'ok': False, 'error': repr(e)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--ratio', type=float, default=0.55)
    args = parser.parse_args()
    
    res = enhance_depth(args.input, args.output, args.ratio)
    print(res)
