import bpy
import json
import math
import random
import os
import sys

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def create_landscape(params):
    # Enable A.N.T.Landscape addon if available
    try:
        bpy.ops.preferences.addon_enable(module="ant_landscape")
        has_ant = True
    except Exception:
        has_ant = False

    size = 50.0
    
    if has_ant:
        try:
            bpy.ops.mesh.landscape_add(
                mesh_size=size,
                mesh_size_y=size,
                random_seed=random.randint(0, 10000),
                noise_type='hetero_terrain',
                noise_depth=8,
                height=5.0,
                water_plane=False
            )
            ground = bpy.context.active_object
        except Exception:
            has_ant = False

    if not has_ant:
        bpy.ops.mesh.primitive_grid_add(size=size, x_subdivisions=100, y_subdivisions=100)
        ground = bpy.context.active_object
        # Add displacement
        tex = bpy.data.textures.new("TerrainNoise", type='CLOUDS')
        tex.noise_scale = 5.0
        tex.noise_depth = 4
        mod = ground.modifiers.new("Displace", 'DISPLACE')
        mod.texture = tex
        mod.strength = 3.0
        # Smooth
        bpy.ops.object.shade_smooth()

    ground.name = "LandscapeGround"
    ground.location = (0, 0, -1.0) # slightly below 0

    # Material
    mat = bpy.data.materials.new(name="LandscapeMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new(type='ShaderNodeOutputMaterial')
    out.location = (400, 0)
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    # Noise color
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 10.0
    
    cr = nodes.new(type='ShaderNodeValToRGB')
    cr.color_ramp.elements[0].position = 0.4
    cr.color_ramp.elements[0].color = (0.05, 0.05, 0.05, 1) # dark rock
    cr.color_ramp.elements[1].position = 0.6
    cr.color_ramp.elements[1].color = (0.2, 0.15, 0.1, 1) # dirt/rock
    
    links.new(noise.outputs['Fac'], cr.inputs['Fac'])
    links.new(cr.outputs['Color'], bsdf.inputs['Base Color'])
    
    bsdf.inputs['Roughness'].default_value = 0.9
    ground.data.materials.append(mat)
    
    return ground

def create_sky():
    # Remove SkyDome generation to avoid the user seeing a giant ball from the outside
    # bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=100.0)
    # sky = bpy.context.active_object
    # sky.name = "SkyDome"
    pass

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    params_json = argv[0] if len(argv) > 0 else "{}"
    output_dir = argv[1] if len(argv) > 1 else "/tmp"
    run_id = argv[2] if len(argv) > 2 else "landscape"
    fmt = argv[3] if len(argv) > 3 else "glb"

    clear_scene()
    
    try:
        params = json.loads(params_json)
    except Exception:
        params = {}

    create_landscape(params)
    create_sky()
    
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
    
    if fmt == "glb":
        bpy.ops.export_scene.gltf(
            filepath=out_file,
            export_format='GLB',
            export_animations=False,
            export_apply=True,
        )
    else:
        bpy.ops.wm.obj_export(filepath=out_file)
    
    # Output JSON for blender_bridge
    print(json.dumps({
        "ok": True,
        "path": out_file,
        "format": fmt,
        "elapsed_s": 0
    }))

if __name__ == "__main__":
    main()
