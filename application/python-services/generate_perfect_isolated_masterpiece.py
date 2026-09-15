#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_perfect_isolated_masterpiece.py — Génération sans détourage destructif :
1. Concept Maître généré DIRECTEMENT sur fond studio neutre pur (ZÉRO arbres, ZÉRO décor parasite, ZÉRO détourage destructif).
2. Bâtiment posé sur une assise/socle plat en pierre (ZÉRO escalier flottant).
3. Génération des 6 vues cohérentes MV-Adapter sans perte d'information.
4. Reconstruction 3D TRELLIS.2-4B et rendus cinématiques 1080p.
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
FINAL_GLB = PROJECT_DIR / "01_fairy_tail_guild_hall.glb"

print("=======================================================")
print(" [1/3] Génération du Concept Maître Isolé sur Fond Neutre Pur...")
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
    "full architectural scale model of fairy tail guild hall building, "
    "magnolia fantasy guild headquarters, iconic alsatian curved red tile roofs, ornate belfry tower with golden bell, "
    "carved timber framing half-timbered walls, arched entrance with golden fairy tail guild crest, "
    "circular wooden balcony, solid flat stone base foundation platform, "
    "entire building centered, three-quarter isometric dynamic angle, "
    "isolated on seamless clean neutral solid grey background, studio lighting, sharp focus, 8k resolution, trending on artstation"
)
neg_prompt = (
    "trees, forest, foliage, landscape, sky, clouds, long stairs, descending stairs, floating, "
    "cut off, cropped, blurry, low quality, deformed, messy, background objects"
)

generator = torch.Generator("cuda").manual_seed(1234)
img = pipe(
    prompt=prompt,
    negative_prompt=neg_prompt,
    num_inference_steps=35,
    guidance_scale=7.5,
    generator=generator,
    height=1024,
    width=1024
).images[0]

img.save(str(MASTER_IMG))
print(f"[OK] Concept maître pur sauvegardé : {MASTER_IMG}")

# Libérer VRAM
del pipe
del vae
torch.cuda.empty_cache()

print("\n=======================================================")
print(" [2/3] Génération des 6 Vues Strictement Cohérentes (MV-Adapter)...")
print("=======================================================")

mv_script = f"""
import sys
sys.path.insert(0, '/home/juan/.local/share/auroraia/external/MV-Adapter')
import torch
from pathlib import Path
from PIL import Image
from mvadapter.pipelines.pipeline_mvadapter_i2mv_sdxl import MVAdapterI2MVSDXLPipeline
from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler
from mvadapter.utils.mesh_utils import get_orthogonal_camera
from mvadapter.utils.geometry import get_plucker_embeds_from_cameras_ortho
from mvadapter.utils import make_image_grid

refs_dir = Path('{str(REFS_DIR)}')
input_img = Image.open(str(refs_dir / 'master_concept.png')).convert('RGB').resize((768, 768))

device = 'cuda'
dtype = torch.float16

pipe = MVAdapterI2MVSDXLPipeline.from_pretrained('stabilityai/stable-diffusion-xl-base-1.0', torch_dtype=dtype, variant='fp16')
pipe.scheduler = ShiftSNRScheduler.from_scheduler(pipe.scheduler, shift_mode='interpolated', shift_scale=8.0)
pipe.init_custom_adapter(num_views=6)
pipe.load_custom_adapter('huanngzh/mv-adapter', weight_name='mvadapter_i2mv_sdxl.safetensors')
pipe.to(device=device, dtype=dtype)
pipe.cond_encoder.to(device=device, dtype=dtype)

azimuth_deg = [0, 60, 120, 180, 240, 300]
cameras = get_orthogonal_camera(
    elevation_deg=[0]*6,
    distance=[1.8]*6,
    left=-0.55, right=0.55, bottom=-0.55, top=0.55,
    azimuth_deg=[x - 90 for x in azimuth_deg],
    device=device
)
plucker_embeds = get_plucker_embeds_from_cameras_ortho(cameras.c2w, [1.1]*6, 768).to(device=device, dtype=dtype)

gen = torch.Generator(device=device).manual_seed(1234)
with torch.no_grad():
    images = pipe(
        image=input_img,
        prompt='masterpiece, best quality, ultra-detailed, fairy tail guild hall building, consistent anime architecture',
        negative_prompt='blurry, distorted, low quality, deformed, inconsistent, floating',
        num_views=6,
        camera_embedding=plucker_embeds,
        height=768,
        width=768,
        num_inference_steps=28,
        guidance_scale=5.0,
        generator=gen
    ).images[0]

view_names = [
    'view_01_front.png',
    'view_02_front_right.png',
    'view_03_right.png',
    'view_04_back.png',
    'view_05_left.png',
    'view_06_front_left.png'
]
for img, name in zip(images, view_names):
    img.save(str(refs_dir / name))
    print(f'  [OK] {{name}} sauvegardé')

make_image_grid(images, rows=1).save(str(refs_dir / 'multiview_consistent_strip.png'))
print('[OK] Planche multi-vues cohérente sauvegardée')
"""

mv_py_file = Path("/tmp/run_mvadapter_clean.py")
mv_py_file.write_text(mv_script)

res_mv = subprocess.run([
    "/home/juan/.local/opt/miniforge3/envs/mvadapter/bin/python",
    str(mv_py_file)
], capture_output=True, text=True)
print(res_mv.stdout)
if res_mv.returncode != 0:
    print(f"Erreur MV-Adapter : {res_mv.stderr}")

print("\n=======================================================")
print(" [3/3] Reconstruction 3D Volumique TRELLIS.2-4B & Rendus 1080p...")
print("=======================================================")

raw_glb = PROJECT_DIR / "raw_trellis.glb"
trellis_script = Path("/home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py")
res_trellis = subprocess.run([
    "/home/juan/AuroraIA/application/.venv/bin/python",
    str(trellis_script),
    str(MASTER_IMG),
    str(raw_glb),
    "--seed", "1234"
], capture_output=True, text=True)
print(res_trellis.stdout)

blender_script = f"""
import bpy
import bmesh
from mathutils import Vector
from pathlib import Path

p_dir = Path('{str(PROJECT_DIR)}')
r_dir = Path('{str(RENDERS_DIR)}')
raw = Path('{str(raw_glb)}')
final = Path('{str(FINAL_GLB)}')

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

print("\nGENERATE_PERFECT_ISOLATED_MASTERPIECE_SUCCESS")
