#!/bin/bash
set -e

PROJECT_DIR="/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall"
REFS_DIR="$PROJECT_DIR/references"
RENDERS_DIR="$PROJECT_DIR/renders"
mkdir -p "$REFS_DIR" "$RENDERS_DIR"

CONCEPT_IMG="$REFS_DIR/master_concept.png"
RAW_GLB="$PROJECT_DIR/raw_trellis.glb"
FINAL_GLB="$PROJECT_DIR/01_fairy_tail_guild_hall.glb"

echo "======================================================="
echo " [1/2] RECONSTRUCTION 3D TRELLIS.2-4B..."
echo "======================================================="
/home/juan/AuroraIA/application/.venv/bin/python /home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py \
  "$CONCEPT_IMG" \
  "$RAW_GLB" \
  --seed 777

echo "======================================================="
echo " [2/2] POST-TRAITEMENT WATERTIGHT & RENDUS 1080P (BLENDER)..."
echo "======================================================="
cat << 'PYEOF' > /tmp/blender_postprocess_sota.py
import bpy
import bmesh
import sys
from pathlib import Path
from mathutils import Vector

project_dir = Path("/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall")
raw_glb = project_dir / "raw_trellis.glb"
final_glb = project_dir / "01_fairy_tail_guild_hall.glb"
renders_dir = project_dir / "renders"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

bpy.ops.import_scene.gltf(filepath=str(raw_glb))

main_obj = None
for obj in scene.objects:
    if obj.type == 'MESH':
        main_obj = obj
        break

if main_obj:
    bbox = [main_obj.matrix_world @ Vector(corner) for corner in main_obj.bound_box]
    min_z = min(v.z for v in bbox)
    min_x, max_x = min(v.x for v in bbox), max(v.x for v in bbox)
    min_y, max_y = min(v.y for v in bbox), max(v.y for v in bbox)
    
    # Socle de fondation étanche
    slab_mesh = bpy.data.meshes.new("FoundationSlab")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(slab_mesh)
    bm.free()
    
    slab_obj = bpy.data.objects.new("FoundationSlab", slab_mesh)
    slab_obj.location = ((min_x + max_x)/2.0, (min_y + max_y)/2.0, min_z - 0.04)
    slab_obj.scale = ((max_x - min_x) * 1.05, (max_y - min_y) * 1.05, 0.08)
    
    mat_base = bpy.data.materials.new("PBR_FoundationStone")
    mat_base.use_nodes = True
    bsdf = mat_base.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.28, 0.26, 0.24, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.85
    slab_obj.data.materials.append(mat_base)
    scene.collection.objects.link(slab_obj)

# Export du modèle officiel final
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(final_glb), export_format='GLB')
if raw_glb.exists():
    raw_glb.unlink()

print(f"[OK] Modèle officiel final exporté : {final_glb}")

# Éclairage Studio & Rendus Cinématiques 1080p
w = bpy.data.worlds.new('StudioWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.05, 0.06, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 0.9

sun1 = bpy.data.objects.new('Sun1', bpy.data.lights.new('Sun1', type='SUN'))
sun1.data.energy = 5.2
sun1.data.color = (1.0, 0.97, 0.92)
sun1.rotation_euler = (0.8, 0.35, -0.65)
scene.collection.objects.link(sun1)

sun2 = bpy.data.objects.new('Sun2', bpy.data.lights.new('Sun2', type='SUN'))
sun2.data.energy = 3.4
sun2.data.color = (0.65, 0.85, 1.0)
sun2.rotation_euler = (0.85, 0.25, 2.45)
scene.collection.objects.link(sun2)

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
cam.data.lens = 42
scene.collection.objects.link(cam)
scene.camera = cam

# Rendu Face
p1 = Vector((2.8, -4.0, 2.6))
cam.location = p1
cam.rotation_euler = (Vector((0, 0, 0.4)) - p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(renders_dir / "render_front.png")
bpy.ops.render.render(write_still=True)
print(f"[OK] Rendu Face : renders/render_front.png")

# Rendu Dos
p2 = Vector((-2.8, 4.0, 2.6))
cam.location = p2
cam.rotation_euler = (Vector((0, 0, 0.4)) - p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(renders_dir / "render_back.png")
bpy.ops.render.render(write_still=True)
print(f"[OK] Rendu Dos : renders/render_back.png")

print("PIPELINE_COMPLETE_SUCCESS")
PYEOF

/home/juan/.local/bin/blender --background --python /tmp/blender_postprocess_sota.py
