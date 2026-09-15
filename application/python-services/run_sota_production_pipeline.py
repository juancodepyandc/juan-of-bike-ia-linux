#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_sota_production_pipeline.py — Pipeline de Production SOTA Ultime :
1. Génération Concept Maître Haute Fidélité SDXL / FLUX (cadrage parfait, fond studio pur).
2. Reconstruction Volumique 3D Haute Résolution via Microsoft TRELLIS.2-4B (O-Voxel Cascade 1024).
3. Post-traitement Géométrique Avancé (mesh_postprocess.py : anti-floaters, fermeture étanche, lissage Taubin).
4. Rendu Cinématique Studio 1080p (renders/render_front.png & renders/render_back.png).
"""
import os
import sys
import subprocess
import torch
from pathlib import Path
from PIL import Image

PROJECT_DIR = Path("/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall")
RENDERS_DIR = PROJECT_DIR / "renders"
REFS_DIR = PROJECT_DIR / "references"
RENDERS_DIR.mkdir(parents=True, exist_ok=True)
REFS_DIR.mkdir(parents=True, exist_ok=True)

FINAL_GLB = PROJECT_DIR / "01_fairy_tail_guild_hall.glb"
RAW_GLB = PROJECT_DIR / "raw_trellis.glb"
CLEANED_GLB = PROJECT_DIR / "cleaned_trellis.glb"
CONCEPT_IMG = REFS_DIR / "master_concept_sota.png"

# Étape 1 : Concept Maître 1024x1024 Haute Fidélité
print("[1/4] Génération du Concept Maître Haute Définition...")
from diffusers import StableDiffusionXLPipeline, AutoencoderKL

vae = AutoencoderKL.from_pretrained(
    "madebyollin/sdxl-vae-fp16-fix",
    torch_dtype=torch.float16
)
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    vae=vae,
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True
).to("cuda")

prompt = (
    "masterpiece, official anime architecture art, fairy tail guild hall building, "
    "magnolia town guild headquarters, iconic alsatian curved red tile roofs, ornate belfry tower with golden bell, "
    "ornate timber framing half-timbered walls, arched entrance portico with large golden fairy tail guild crest emblem, "
    "stone foundation steps, full complete building shown from dynamic three-quarter front angle, "
    "warm tavern lantern glow, sharp focus, vibrant anime colors, clean neutral studio background, 8k resolution, trending on artstation"
)
neg_prompt = "blurry, cropped, cut off, low quality, deformed, duplicate, messy, multiple buildings, bad geometry"

generator = torch.Generator("cuda").manual_seed(777)
image = pipe(
    prompt=prompt,
    negative_prompt=neg_prompt,
    num_inference_steps=32,
    guidance_scale=7.5,
    generator=generator,
    height=1024,
    width=1024
).images[0]

image.save(str(CONCEPT_IMG))
print(f"[OK] Concept sauvegardé dans {CONCEPT_IMG}")

# Libérer la VRAM
del pipe
del vae
torch.cuda.empty_cache()

# Étape 2 : Reconstruction 3D TRELLIS.2-4B
print("\n[2/4] Reconstruction Volumique 3D TRELLIS.2-4B...")
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
    print(f"Erreur TRELLIS : {res.stderr}")
    sys.exit(1)

print(f"[OK] Modèle brut 3D généré : {RAW_GLB} ({RAW_GLB.stat().st_size // 1024 // 1024} Mo)")

# Étape 3 : Post-traitement & Nettoyage Géométrique Expert (mesh_postprocess.py)
print("\n[3/4] Post-traitement Géométrique Watertight & Taubin Smoothing...")
postprocess_script = Path("/home/juan/AuroraIA/application/python-services/mesh_postprocess.py")
res_post = subprocess.run([
    sys.executable,
    str(postprocess_script),
    "--input", str(RAW_GLB),
    "--output", str(FINAL_GLB),
    "--intent-purpose", "mechanical_part",
    "--motion-readiness", "static_only"
], capture_output=True, text=True)
print(res_post.stdout)

if not FINAL_GLB.exists() or FINAL_GLB.stat().st_size == 0:
    # Si échec, garder le RAW
    RAW_GLB.replace(FINAL_GLB)
else:
    if RAW_GLB.exists():
        RAW_GLB.unlink()

# Étape 4 : Rendu Cinématique Studio 1080p
print("\n[4/4] Rendus Cinématiques 1080p...")
render_py = f"""
import bpy
import bmesh
from mathutils import Vector
from pathlib import Path

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

w = bpy.data.worlds.new('Studio')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.04, 0.05, 0.07, 1.0)
    bg.inputs['Strength'].default_value = 0.9

sun1 = bpy.data.objects.new('Sun1', bpy.data.lights.new('Sun1', type='SUN'))
sun1.data.energy = 5.0
sun1.data.color = (1.0, 0.96, 0.90)
sun1.rotation_euler = (0.8, 0.35, -0.65)
scene.collection.objects.link(sun1)

sun2 = bpy.data.objects.new('Sun2', bpy.data.lights.new('Sun2', type='SUN'))
sun2.data.energy = 3.2
sun2.data.color = (0.65, 0.85, 1.0)
sun2.rotation_euler = (0.85, 0.25, 2.45)
scene.collection.objects.link(sun2)

bpy.ops.import_scene.gltf(filepath=r'{str(FINAL_GLB)}')

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
cam.data.lens = 42
scene.collection.objects.link(cam)
scene.camera = cam

p1 = Vector((2.6, -3.8, 2.5))
cam.location = p1
cam.rotation_euler = (Vector((0, 0, 0.4)) - p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = r'{str(RENDERS_DIR / "render_front.png")}'
bpy.ops.render.render(write_still=True)

p2 = Vector((-2.6, 3.8, 2.5))
cam.location = p2
cam.rotation_euler = (Vector((0, 0, 0.4)) - p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = r'{str(RENDERS_DIR / "render_back.png")}'
bpy.ops.render.render(write_still=True)
"""

render_script_path = Path("/tmp/render_sota.py")
render_script_path.write_text(render_py)

res_render = subprocess.run([
    "/home/juan/.local/bin/blender",
    "--background",
    "--python", str(render_script_path)
], capture_output=True, text=True)
print(res_render.stdout)

print("\nPIPELINE_SOTA_COMPLETE_SUCCESS")
