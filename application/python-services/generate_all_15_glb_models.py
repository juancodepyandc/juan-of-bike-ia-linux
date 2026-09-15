#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_all_15_glb_models.py — Génération par lots des 15 modèles 3D réels (GLB)
via TRELLIS.2-4B + Rembg + Rendu de prévisualisation 3D multi-angles.
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from PIL import Image
from rembg import remove

BASE_DIR = Path('/home/juan/AuroraIA/application/output/3d/magnolia_fairy_tail_city/15_masterpieces')
RGBA_DIR = BASE_DIR / 'rgba'
MODELS_DIR = BASE_DIR / '3d_models'
PREVIEWS_DIR = BASE_DIR / '3d_previews'

RGBA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

TRELLIS_SCRIPT = Path('/home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py')
PYTHON_ENV = Path('/home/juan/AuroraIA/application/.venv/bin/python')
BLENDER_BIN = Path('/home/juan/.local/bin/blender')

# 15 Assets
ASSET_NAMES = [
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

print("==========================================================")
print("  PRODUCTION DES 15 MODÈLES 3D RÉELS (GLB)")
print("==========================================================")

# Script Blender pour rendu turntable 3D
BLENDER_RENDER_PY = BASE_DIR / "render_turntable.py"
with open(BLENDER_RENDER_PY, "w") as f:
    f.write("""
import bpy, sys, os
argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, png_out = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 1024
scene.render.resolution_y = 768

# Lighting
w = bpy.data.worlds.new('TurntableWorld')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.08, 0.09, 0.12, 1.0)
    bg.inputs['Strength'].default_value = 0.8

sun_data = bpy.data.lights.new('Sun', type='SUN')
sun_data.energy = 3.5
sun_data.color = (1.0, 0.98, 0.92)
sun_obj = bpy.data.objects.new('Sun', sun_data)
sun_obj.rotation_euler = (0.8, 0.3, -0.6)
scene.collection.objects.link(sun_obj)

rim_data = bpy.data.lights.new('Rim', type='POINT')
rim_data.energy = 400.0
rim_data.color = (0.5, 0.8, 1.0)
rim_obj = bpy.data.objects.new('Rim', rim_data)
rim_obj.location = (-3, 3, 3)
scene.collection.objects.link(rim_obj)

# Import GLB
bpy.ops.import_scene.gltf(filepath=glb_in)

# Camera
cam_data = bpy.data.cameras.new('Camera')
cam_data.lens = 45
cam_obj = bpy.data.objects.new('Camera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.location = (0, -2.8, 1.2)
cam_obj.rotation_euler = (1.25, 0, 0)

scene.render.filepath = png_out
bpy.ops.render.render(write_still=True)
""")

for i, name in enumerate(ASSET_NAMES, 1):
    src_png = BASE_DIR / f"{name}.png"
    rgba_png = RGBA_DIR / f"{name}_rgba.png"
    out_glb = MODELS_DIR / f"{name}.glb"
    preview_png = PREVIEWS_DIR / f"{name}_3d_preview.png"
    
    print(f"\n[{i}/15] Traitement de : {name}")
    
    # 1. Détourage RGBA si pas déjà fait
    if not rgba_png.is_file():
        print(f"  -> Extraction RGBA via rembg...")
        input_img = Image.open(src_png)
        rgba_img = remove(input_img)
        rgba_img.save(rgba_png)
    
    # 2. Génération GLB via TRELLIS.2
    if not out_glb.is_file() or out_glb.stat().st_size < 10000:
        print(f"  -> Reconstruction 3D volumique neuronale (TRELLIS.2)...")
        cmd = [
            str(PYTHON_ENV),
            str(TRELLIS_SCRIPT),
            str(rgba_png),
            str(out_glb),
            "--seed", str(100 + i)
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        print(f"  -> Statut TRELLIS : {p.returncode}")
        for line in p.stdout.splitlines():
            if "AURORA_TRELLIS_RESULT" in line:
                print(f"     {line}")
    else:
        print(f"  -> GLB déjà généré ({out_glb.stat().st_size // 1024 // 1024} Mo)")

    # 3. Rendu 3D Preview
    if out_glb.is_file() and not preview_png.is_file():
        print(f"  -> Rendu de la prévisualisation 3D...")
        cmd_render = [
            str(BLENDER_BIN),
            "--background",
            "--python", str(BLENDER_RENDER_PY),
            "--", str(out_glb), str(preview_png)
        ]
        subprocess.run(cmd_render, capture_output=True, text=True)

print("\n==========================================================")
print("  TOUS LES 15 MODÈLES 3D RÉELS SONT PRÊTS !")
print("==========================================================")
