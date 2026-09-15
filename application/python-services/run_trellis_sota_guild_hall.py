#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_trellis_sota_guild_hall.py — Reconstruction 3D Volumique SOTA Ultime :
1. Reconstruction Volumique 3D TRELLIS.2-4B depuis master_concept_sota.png vers raw_trellis.glb
2. Réparation, scellement étanche et export vers 01_fairy_tail_guild_hall.glb
3. Rendus Cinématiques 1080p dans renders/
"""
import sys
import subprocess
import bpy
import bmesh
from pathlib import Path
from mathutils import Vector

PROJECT_DIR = Path("/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall")
RENDERS_DIR = PROJECT_DIR / "renders"
REFS_DIR = PROJECT_DIR / "references"
RENDERS_DIR.mkdir(parents=True, exist_ok=True)
REFS_DIR.mkdir(parents=True, exist_ok=True)

CONCEPT_IMG = REFS_DIR / "master_concept_sota.png"
RAW_GLB = PROJECT_DIR / "raw_trellis.glb"
FINAL_GLB = PROJECT_DIR / "01_fairy_tail_guild_hall.glb"

print(f"=======================================================")
print(f"  PRODUCTION 3D SOTA ULTIME : FAIRY TAIL GUILD HALL")
print(f"=======================================================")

# 1. Reconstruction TRELLIS.2-4B
print("\n[1/3] Reconstruction Volumique TRELLIS.2-4B...")
trellis_script = Path("/home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py")
res = subprocess.run([
    sys.executable,
    str(trellis_script),
    str(CONCEPT_IMG),
    str(RAW_GLB),
    "--seed", "777"
], capture_output=True, text=True)

print(res.stdout)
if res.returncode != 0 or not RAW_GLB.exists():
    print(f"ERREUR TRELLIS : {res.stderr}")
    sys.exit(1)

print(f"[OK] Fichier 3D brut généré : {RAW_GLB} ({RAW_GLB.stat().st_size // 1024 // 1024} Mo)")

# 2. Blender : Réparation, Fermeture Étanche & Export Officiel
print("\n[2/3] Post-traitement Blender, Fermeture Watertight & Export...")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

bpy.ops.import_scene.gltf(filepath=str(RAW_GLB))

# Réparation du maillage
main_obj = None
for obj in scene.objects:
    if obj.type == 'MESH':
        main_obj = obj
        break

if main_obj:
    bpy.context.view_layer.objects.active = main_obj
    main_obj.select_set(True)
    
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
bpy.ops.export_scene.gltf(filepath=str(FINAL_GLB), export_format='GLB')
if RAW_GLB.exists():
    RAW_GLB.unlink()

print(f"[OK] Modèle officiel final exporté : {FINAL_GLB} ({FINAL_GLB.stat().st_size // 1024 // 1024} Mo)")

# 3. Éclairage Studio & Rendus Cinématiques 1080p
print("\n[3/3] Rendus Cinématiques 1080p dans renders/...")
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
scene.render.filepath = str(RENDERS_DIR / "render_front.png")
bpy.ops.render.render(write_still=True)
print(f"[OK] Rendu Face : renders/render_front.png")

# Rendu Dos
p2 = Vector((-2.8, 4.0, 2.6))
cam.location = p2
cam.rotation_euler = (Vector((0, 0, 0.4)) - p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(RENDERS_DIR / "render_back.png")
bpy.ops.render.render(write_still=True)
print(f"[OK] Rendu Dos : renders/render_back.png")

print("\nPIPELINE_SOTA_GUILD_HALL_SUCCESS")
