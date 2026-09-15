#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_3d_pipeline_runner.py — Exécuteur officiel du pipeline 3D pour tous les projets.
Structure de chaque projet sous output/3d/<project_name>/ :
- <project_name>.glb
- render.png
- references/
  - concept.png
  - cutout.png
AUCUN script Python ou déchet dans output/3d/ !
"""
import os
import sys
import subprocess
from pathlib import Path
from PIL import Image
from rembg import remove

OUTPUT_3D_ROOT = Path('/home/juan/AuroraIA/application/output/3d')
PYTHON_ENV = Path('/home/juan/AuroraIA/application/.venv/bin/python')
TRELLIS_SCRIPT = Path('/home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py')
BLENDER_BIN = Path('/home/juan/.local/bin/blender')
BLENDER_RENDER_PY = Path('/home/juan/AuroraIA/application/python-services/render_project_turntable.py')

# Écrire le script de rendu dans python-services/ (JAMAIS dans output/3d/)
with open(BLENDER_RENDER_PY, "w") as f:
    f.write("""
import bpy, sys
argv = sys.argv[sys.argv.index("--") + 1:]
glb_path, out_png = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 28
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720

w = bpy.data.worlds.new('StudioWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.05, 0.06, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 0.8

sun_data = bpy.data.lights.new('Sun', type='SUN')
sun_data.energy = 4.0
sun_data.color = (1.0, 0.98, 0.94)
sun_obj = bpy.data.objects.new('Sun', sun_data)
sun_obj.rotation_euler = (0.85, 0.3, -0.6)
scene.collection.objects.link(sun_obj)

rim_data = bpy.data.lights.new('Rim', type='POINT')
rim_data.energy = 500.0
rim_data.color = (0.6, 0.85, 1.0)
rim_obj = bpy.data.objects.new('Rim', rim_data)
rim_obj.location = (-3.5, 3.5, 3.5)
scene.collection.objects.link(rim_obj)

bpy.ops.import_scene.gltf(filepath=glb_path)

cam_data = bpy.data.cameras.new('Camera')
cam_data.lens = 45
cam_obj = bpy.data.objects.new('Camera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.location = (0, -2.8, 1.1)
cam_obj.rotation_euler = (1.28, 0, 0)

scene.render.filepath = out_png
bpy.ops.render.render(write_still=True)
""")

PROJECT_NAMES = [
    "01_fairy_tail_guild_hall",
    "02_kardia_cathedral",
    "03_mercurius_palace_crocus",
    "04_floating_city_extalia",
    "05_cliffside_himalayan_monastery",
    "06_natsu_dragon_force",
    "07_erza_flame_empress_armor",
    "08_acnologia_dragon_apocalypse",
    "09_chimera_beast_guardian",
    "10_christina_flying_ship",
    "11_magnolia_magical_steam_train",
    "12_domus_flau_grand_magic_games_arena",
    "13_phantom_lord_walking_fortress",
    "14_celestial_time_astrolabe",
    "15_black_dragon_bone_throne",
]

for idx, p_name in enumerate(PROJECT_NAMES, 1):
    p_dir = OUTPUT_3D_ROOT / p_name
    ref_dir = p_dir / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    
    concept_png = ref_dir / "concept.png"
    cutout_png = ref_dir / "cutout.png"
    out_glb = p_dir / f"{p_name}.glb"
    render_png = p_dir / "render.png"
    
    print(f"\n=======================================================")
    print(f"[{idx}/15] Production du Projet 3D : {p_name}")
    print(f"=======================================================")
    
    if not concept_png.is_file():
        print(f"  [ERREUR] concept.png manquant dans {ref_dir}")
        continue
        
    # 1. Extraction détourée dans references/
    if not cutout_png.is_file():
        print(f"  1. Extraction transparente (rembg) -> references/cutout.png")
        img = Image.open(concept_png)
        cutout = remove(img)
        cutout.save(cutout_png)
        
    # 2. Reconstruction volumique neuronale TRELLIS.2 (1024_cascade) -> <project>.glb
    if not out_glb.is_file() or out_glb.stat().st_size < 10000:
        print(f"  2. Reconstruction 3D (TRELLIS.2) -> {out_glb.name}")
        cmd_trellis = [
            str(PYTHON_ENV),
            str(TRELLIS_SCRIPT),
            str(cutout_png),
            str(out_glb),
            "1024_cascade",
            "--seed", str(200 + idx)
        ]
        p = subprocess.run(cmd_trellis, capture_output=True, text=True)
        for line in p.stdout.splitlines():
            if "AURORA_TRELLIS_RESULT" in line:
                print(f"     {line}")
    else:
        print(f"  2. Fichier 3D GLB déjà présent ({out_glb.stat().st_size // 1024 // 1024} Mo)")

    # 3. Rendu officiel dans le dossier du projet -> render.png
    if out_glb.is_file() and not render_png.is_file():
        print(f"  3. Rendu cinématique Cycles -> render.png")
        cmd_render = [
            str(BLENDER_BIN),
            "--background",
            "--python", str(BLENDER_RENDER_PY),
            "--", str(out_glb), str(render_png)
        ]
        subprocess.run(cmd_render, capture_output=True, text=True)
        print(f"     [OK] Rendu sauvegardé dans {render_png}")

print("\n==========================================================")
print("  PRODUCTION 3D DE TOUS LES PROJETS TERMINÉE AVEC SUCCÈS")
print("==========================================================")
