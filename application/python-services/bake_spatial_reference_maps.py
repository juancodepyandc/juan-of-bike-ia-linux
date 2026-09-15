import bpy
import os

GLB_PATH = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_mesh.glb"
OUT_DIR = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/maps"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

ob = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.shade_smooth()

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "GPU"
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = "EMIT"

def bake_node_output(name, node_setup_fn, width=4096, height=4096):
    img = bpy.data.images.new(name, width=width, height=height)
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_emit = nodes.new("ShaderNodeEmission")
    mat.node_tree.links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
    
    node_setup_fn(mat, nodes, n_emit)
    
    n_target = nodes.new("ShaderNodeTexImage")
    n_target.image = img
    nodes.active = n_target
    
    ob.active_material = mat
    print(f"Baking {name}...")
    bpy.ops.object.bake(type="EMIT")
    
    out_path = os.path.join(OUT_DIR, f"{name}.png")
    img.filepath_raw = out_path
    img.file_format = 'PNG'
    img.save()
    print(f"Saved: {out_path}")

# 1. Z Position Normalized Map (0..1)
def setup_z_pos(mat, nodes, n_emit):
    geom = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    mat.node_tree.links.new(geom.outputs["Position"], sep.inputs["Vector"])
    
    # map Z from [-1.0, 1.0] to [0.0, 1.0]
    map_range = nodes.new("ShaderNodeMapRange")
    map_range.inputs["From Min"].default_value = -1.0
    map_range.inputs["From Max"].default_value = 1.0
    map_range.inputs["To Min"].default_value = 0.0
    map_range.inputs["To Max"].default_value = 1.0
    mat.node_tree.links.new(sep.outputs["Z"], map_range.inputs["Value"])
    mat.node_tree.links.new(map_range.outputs["Result"], n_emit.inputs["Color"])

# 2. Curvature / Pointiness (Cavity for hair curls)
def setup_curvature(mat, nodes, n_emit):
    geom = nodes.new("ShaderNodeNewGeometry")
    # Pointiness
    gamma = nodes.new("ShaderNodeGamma")
    gamma.inputs["Gamma"].default_value = 1.5
    mat.node_tree.links.new(geom.outputs["Pointiness"], gamma.inputs["Color"])
    mat.node_tree.links.new(gamma.outputs["Color"], n_emit.inputs["Color"])

bake_node_output("pos_z_map", setup_z_pos)
bake_node_output("pointiness_map", setup_curvature)

print("ALL SPATIAL MAPS BAKED SUCCESSFULLY!")
