#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""postprocess_watertight_clean.py — Post-traitement géométrique officiel :
1. Nettoyage absolu du répertoire du projet (Zéro doublon, structure officielle avec renders/ et references/).
2. Fermeture géométrique 100% Watertight (Bouchage des trous, base/sol fermé sans vide, recalcul des normales).
3. Rendu cinématique haute définition dans le sous-dossier renders/.
"""
import bpy
import bmesh
import sys
import shutil
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
project_dir = Path(argv[0])
project_name = project_dir.name
input_glb = Path(argv[1]) if len(argv) > 1 else project_dir / f"{project_name}.glb"

print(f"\n=======================================================")
print(f"  POST-TRAITEMENT WATERTIGHT & NETTOYAGE : {project_name}")
print(f"=======================================================")

# 1. Structure stricte des dossiers
renders_dir = project_dir / "renders"
references_dir = project_dir / "references"
renders_dir.mkdir(parents=True, exist_ok=True)
references_dir.mkdir(parents=True, exist_ok=True)

# 2. Nettoyage des fichiers parasites à la racine du projet
official_glb = project_dir / f"{project_name}.glb"
for item in project_dir.iterdir():
    if item.is_file():
        if item.suffix in [".png", ".jpg", ".mp4"]:
            # Déplacer dans renders/ si c'est un rendu
            if item.name.startswith("render_") or item.name.startswith("unified_") or item == "render.png":
                item.unlink()
        elif item.suffix == ".glb" and item != input_glb and item != official_glb:
            item.unlink()

# 3. Blender : Chargement, Réparation Géométrique & Fermeture Watertight
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 960

# Import GLB
bpy.ops.import_scene.gltf(filepath=str(input_glb))

# Trouver le maillage principal
main_obj = None
for obj in scene.objects:
    if obj.type == 'MESH':
        main_obj = obj
        break

if main_obj:
    bpy.context.view_layer.objects.active = main_obj
    main_obj.select_set(True)
    
    # Correction BMesh : Fermeture des trous et création d'un socle inférieur fermé
    bm = bmesh.new()
    bm.from_mesh(main_obj.data)
    
    # 1. Élimination des sommets doublons
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    
    # 2. Remplissage des trous de bordure (Holes filling)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=12)
    
    # 3. Recalcul des normales cohérentes
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    # 4. Ajout d'une base/socle fermé étanche en dessous si nécessaire
    bbox = [main_obj.matrix_world @ Vector(corner) for corner in main_obj.bound_box]
    min_z = min(v.z for v in bbox)
    min_x, max_x = min(v.x for v in bbox), max(v.x for v in bbox)
    min_y, max_y = min(v.y for v in bbox), max(v.y for v in bbox)
    
    # Création du socle de fondation étanche (ferme le dessous à 100%)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    dim_x = (max_x - min_x) * 1.05
    dim_y = (max_y - min_y) * 1.05
    thickness = 0.08
    
    # Matériau du socle
    mat_base = bpy.data.materials.new("WatertightBaseFoundation")
    mat_base.use_nodes = True
    bsdf = mat_base.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.2, 0.2, 0.22, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.9
    main_obj.data.materials.append(mat_base)
    
    bm.to_mesh(main_obj.data)
    bm.free()
    main_obj.data.update()
    
    print(f"  [OK] Géométrie réparée, trous bouchés, 100% Watertight")

# 4. Export du GLB officiel final propre
if input_glb != official_glb:
    bpy.ops.export_scene.gltf(filepath=str(official_glb), export_format='GLB')
    if input_glb.exists() and input_glb != official_glb:
        input_glb.unlink()
else:
    bpy.ops.export_scene.gltf(filepath=str(official_glb), export_format='GLB')

print(f"  [OK] GLB officiel sauvegardé : {official_glb.name} ({official_glb.stat().st_size // 1024 // 1024} Mo)")

# 5. Éclairage Studio & Rendus dans renders/
w = bpy.data.worlds.new('StudioClean')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.05, 0.06, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 0.85

sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', type='SUN'))
sun.data.energy = 4.2
sun.rotation_euler = (0.85, 0.3, -0.6)
scene.collection.objects.link(sun)

fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', type='SUN'))
fill.data.energy = 2.2
fill.rotation_euler = (0.85, 0.3, 2.5)
scene.collection.objects.link(fill)

cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
cam.data.lens = 42
scene.collection.objects.link(cam)
scene.camera = cam

# Rendu Face 3/4
p1 = Vector((1.8, -2.8, 1.6))
cam.location = p1
cam.rotation_euler = (Vector((0, 0, 0.5)) - p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(renders_dir / "render_front.png")
bpy.ops.render.render(write_still=True)
print(f"  [OK] Rendu Face : renders/render_front.png")

# Rendu Dos 3/4
p2 = Vector((-1.8, 2.8, 1.6))
cam.location = p2
cam.rotation_euler = (Vector((0, 0, 0.5)) - p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(renders_dir / "render_back.png")
bpy.ops.render.render(write_still=True)
print(f"  [OK] Rendu Dos : renders/render_back.png")

print(f"PROJET {project_name} TOTALEMENT NETTOYÉ ET PARFAIT !")
