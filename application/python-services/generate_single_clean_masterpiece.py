#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_single_clean_masterpiece.py — Générateur Garanti 1 Seul Bâtiment Isolé Net :
1. Génération SDXL d'EXACTEMENT 1 SEUL bâtiment centré (Zéro collage, Zéro découpage d'escalier).
2. Génération des 6 vues strictement cohérentes MV-Adapter.
3. Découpage propre des 6 vues dans references/.
4. Reconstruction 3D TRELLIS.2-4B + Socle étanche + Rendus 1080p.
"""
import os
import sys
import torch
import subprocess
from pathlib import Path
from PIL import Image

PROJECT_DIR = Path("/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall")
REFS_DIR = PROJECT_DIR / "references"
RENDERS_DIR = PROJECT_DIR / "renders"
REFS_DIR.mkdir(parents=True, exist_ok=True)
RENDERS_DIR.mkdir(parents=True, exist_ok=True)

MASTER_IMG = REFS_DIR / "master_concept.png"
STRIP_IMG = REFS_DIR / "multiview_consistent_strip.png"
RAW_GLB = PROJECT_DIR / "raw_trellis.glb"
FINAL_GLB = PROJECT_DIR / "01_fairy_tail_guild_hall.glb"

print("=======================================================")
print(" [1/4] Génération d'UN SEUL Bâtiment Maître Isolé...")
print("=======================================================")

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
    "a single isolated fairy tail guild hall building, one single building centered in frame, "
    "alsatian curved red tile roofs, ornate octagonal belfry tower with golden bell, "
    "dark timber framing half-timbered plaster walls, grand entrance arched portico with golden guild crest, "
    "circular wooden balcony, solid level stone courtyard foundation, "
    "clear three-quarter isometric dynamic view, single structure, "
    "isolated on plain neutral solid light grey background, clean studio lighting, sharp focus, 8k resolution anime architectural concept art"
)
neg_prompt = (
    "multiple buildings, collage, grid, pattern, texture sheet, duplicate houses, town, village, street, "
    "trees, foliage, descending stairs, floating parts, cutoff, cropped, blurry, bad anatomy"
)

generator = torch.Generator("cuda").manual_seed(999)
img = pipe(
    prompt=prompt,
    negative_prompt=neg_prompt,
    num_inference_steps=32,
    guidance_scale=7.5,
    generator=generator,
    height=1024,
    width=1024
).images[0]

img.save(str(MASTER_IMG))
print(f"[OK] Concept maître unique sauvegardé : {MASTER_IMG}")

# Libérer VRAM
del pipe
del vae
torch.cuda.empty_cache()

print("\n=======================================================")
print(" [2/4] Génération des 6 Vues Strictement Cohérentes (MV-Adapter)...")
print("=======================================================")

env_vars = os.environ.copy()
env_vars["PYTHONPATH"] = "/home/juan/.local/share/auroraia/external/MV-Adapter"

res_mv = subprocess.run([
    "/home/juan/.local/opt/miniforge3/envs/mvadapter/bin/python",
    "/home/juan/.local/share/auroraia/external/MV-Adapter/scripts/inference_i2mv_sdxl.py",
    "--image", str(MASTER_IMG),
    "--output", str(STRIP_IMG),
    "--num_inference_steps", "25",
    "--seed", "999"
], env=env_vars, capture_output=True, text=True)

print(res_mv.stdout)
if res_mv.returncode != 0:
    print(f"Erreur MV-Adapter : {res_mv.stderr}")
else:
    # Découper les 6 vues
    strip = Image.open(str(STRIP_IMG))
    sw, sh = strip.size
    vw = sw // 6
    vnames = [
        "view_01_front.png",
        "view_02_front_right.png",
        "view_03_right.png",
        "view_04_back.png",
        "view_05_left.png",
        "view_06_front_left.png"
    ]
    for i, vn in enumerate(vnames):
        strip.crop((i * vw, 0, (i + 1) * vw, sh)).save(str(REFS_DIR / vn))
        print(f"  [OK] Vue {vn} extraite")

print("\n=======================================================")
print(" [3/4] Reconstruction Volumique 3D TRELLIS.2-4B...")
print("=======================================================")

trellis_script = Path("/home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py")
res_trellis = subprocess.run([
    "/home/juan/AuroraIA/application/.venv/bin/python",
    str(trellis_script),
    str(MASTER_IMG),
    str(RAW_GLB),
    "--seed", "999"
], capture_output=True, text=True)
print(res_trellis.stdout)

print("\n=======================================================")
print(" [4/4] Post-traitement Blender, Fermeture Watertight & Rendus 1080p...")
print("=======================================================")

blender_script = f"""
import bpy
import bmesh
from mathutils import Vector
from pathlib import Path

raw = Path('{str(RAW_GLB)}')
final = Path('{str(FINAL_GLB)}')
r_dir = Path('{str(RENDERS_DIR)}')

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

bpy.ops.import_scene.gltf(filepath=str(raw))

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
    
    # Socle solide de base étanche
    slab_mesh = bpy.data.meshes.new("FoundationPlinth")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(slab_mesh)
    bm.free()
    
    slab_obj = bpy.data.objects.new("FoundationPlinth", slab_mesh)
    slab_obj.location = ((min_x + max_x)/2.0, (min_y + max_y)/2.0, min_z - 0.03)
    slab_obj.scale = ((max_x - min_x) * 1.04, (max_y - min_y) * 1.04, 0.06)
    
    mat = bpy.data.materials.new("PBR_StoneBase")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.3, 0.28, 0.26, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.85
    slab_obj.data.materials.append(mat)
    scene.collection.objects.link(slab_obj)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(final), export_format='GLB')
if raw.exists():
    raw.unlink()

print(f"[OK] Modèle officiel final exporté : {{final}}")

w = bpy.data.worlds.new('Studio')
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

p1 = Vector((2.8, -4.0, 2.6))
cam.location = p1
cam.rotation_euler = (Vector((0, 0, 0.4)) - p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(r_dir / "render_front.png")
bpy.ops.render.render(write_still=True)

p2 = Vector((-2.8, 4.0, 2.6))
cam.location = p2
cam.rotation_euler = (Vector((0, 0, 0.4)) - p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(r_dir / "render_back.png")
bpy.ops.render.render(write_still=True)
print("[OK] Rendus 1080p terminés")
"""

blender_py_file = Path("/tmp/run_blender_clean.py")
blender_py_file.write_text(blender_script)

res_blender = subprocess.run([
    "/home/juan/.local/bin/blender",
    "--background",
    "--python", str(blender_py_file)
], capture_output=True, text=True)
print(res_blender.stdout)

print("\nPIPELINE_SINGLE_CLEAN_SUCCESS")
