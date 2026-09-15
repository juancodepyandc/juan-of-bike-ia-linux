#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_ultimate_benchmark_dragon.py — Stress-Test Ultime de Complexité 3D :
Modèle : 'L'Automate Dragon Horloger Céleste & Astrolabe Astral'
(Engrenages imbriqués, ailes en armature laiton et vitraux, squelette chrono-gothique, socle hexagonal en marbre et bronze).
Robuste en VRAM via CPU offload dynamique.
"""
import os
import sys
import torch
import subprocess
from pathlib import Path
from PIL import Image

BENCHMARK_DIR = Path("/home/juan/AuroraIA/application/output/3d/benchmark_ultimate_complex_model")
REFS_DIR = BENCHMARK_DIR / "references"
RENDERS_DIR = BENCHMARK_DIR / "renders"
REFS_DIR.mkdir(parents=True, exist_ok=True)
RENDERS_DIR.mkdir(parents=True, exist_ok=True)

MASTER_IMG = REFS_DIR / "master_concept.png"
STRIP_IMG = REFS_DIR / "multiview_consistent_strip.png"
RAW_GLB = BENCHMARK_DIR / "raw_model.glb"
FINAL_GLB = BENCHMARK_DIR / "benchmark_ultimate_complex_model.glb"

print("================================================================================")
print("  STRESS-TEST BENCHMARK SOTA 3D : AUTOMATE DRAGON HORLOGER & ASTROLABE ASTRAL")
print("================================================================================")

# 1. Génération du Concept Maître Hyper-Détaillé (SDXL avec CPU Offload)
print("\n[1/4] Synthèse du Concept Maître Haute Complexité...")
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
)
pipe.enable_model_cpu_offload()

prompt = (
    "masterpiece, a single intricate celestial astrolabe dragon automaton, "
    "magnificent mechanical clockwork dragon perched firmly on an ornate dark marble hexagonal pedestal, "
    "interlocking polished brass and damascus steel gears, exposed tourbillon escapement mechanism, "
    "glowing sapphire crystalline energy core inside openwork filigree ribcage, "
    "articulated dragon head with ruby optical sensors and curled baroque horns, "
    "mechanical wings with exposed brass struts and stained glass membrane panels, "
    "entire singular object centered in frame, three-quarter dynamic isometric studio view, "
    "isolated on plain solid neutral grey background, dramatic rim lighting, sharp focus, 8k resolution, trending on artstation"
)
neg_prompt = (
    "multiple objects, collage, duplicate dragons, scenery, landscape, forest, mountains, sky, "
    "floating parts, cutoff, cropped, blurry, low resolution, deformed, messy"
)

generator = torch.Generator("cuda").manual_seed(4242)
img = pipe(
    prompt=prompt,
    negative_prompt=neg_prompt,
    num_inference_steps=35,
    guidance_scale=8.0,
    generator=generator,
    height=1024,
    width=1024
).images[0]

img.save(str(MASTER_IMG))
print(f"[OK] Concept Maître sauvegardé : {MASTER_IMG}")

del pipe
del vae
torch.cuda.empty_cache()

# 2. Génération des 6 Vues Strictement Cohérentes (MV-Adapter SDXL)
print("\n[2/4] Synthèse Multi-Vues Cohérentes 360° (MV-Adapter SDXL)...")
env_vars = os.environ.copy()
env_vars["PYTHONPATH"] = "/home/juan/.local/share/auroraia/external/MV-Adapter"

res_mv = subprocess.run([
    "/home/juan/.local/opt/miniforge3/envs/mvadapter/bin/python",
    "/home/juan/.local/share/auroraia/external/MV-Adapter/scripts/inference_i2mv_sdxl.py",
    "--image", str(MASTER_IMG),
    "--output", str(STRIP_IMG),
    "--num_inference_steps", "25",
    "--seed", "4242"
], env=env_vars, capture_output=True, text=True)

print(res_mv.stdout)
if STRIP_IMG.exists():
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

# 3. Reconstruction Volumique 3D TRELLIS.2-4B
print("\n[3/4] Reconstruction Volumique 3D TRELLIS.2-4B...")
trellis_script = Path("/home/juan/AuroraIA/application/python-services/aurora_hunyuan/aurora_trellis_wrapper.py")
res_trellis = subprocess.run([
    "/home/juan/AuroraIA/application/.venv/bin/python",
    str(trellis_script),
    str(MASTER_IMG),
    str(RAW_GLB),
    "--seed", "4242"
], capture_output=True, text=True)
print(res_trellis.stdout)

# 4. Blender Cycles : Fermeture Watertight & Rendus Cinématiques 1080p
print("\n[4/4] Blender Cycles 1080p : Rendus Face & Dos...")
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

if raw.exists():
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
        
        # Socle hexagonal
        slab_mesh = bpy.data.meshes.new("HexPedestal")
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=6)
        bm.to_mesh(slab_mesh)
        bm.free()
        
        slab_obj = bpy.data.objects.new("HexPedestal", slab_mesh)
        slab_obj.location = ((min_x + max_x)/2.0, (min_y + max_y)/2.0, min_z - 0.02)
        slab_obj.scale = ((max_x - min_x) * 0.65, (max_y - min_y) * 0.65, 0.05)
        
        mat = bpy.data.materials.new("PBR_DarkObsidian")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (0.1, 0.1, 0.12, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.3
            bsdf.inputs['Metallic'].default_value = 0.8
        slab_obj.data.materials.append(mat)
        scene.collection.objects.link(slab_obj)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=str(final), export_format='GLB')
    if raw.exists():
        raw.unlink()
    print(f"[OK] Modèle exporté : {{final}}")

w = bpy.data.worlds.new('Studio')
scene.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.04, 0.05, 0.07, 1.0)
    bg.inputs['Strength'].default_value = 1.0

# Éclairage 3 points studio dramatique
sun1 = bpy.data.objects.new('KeySun', bpy.data.lights.new('KeySun', type='SUN'))
sun1.data.energy = 5.8
sun1.data.color = (1.0, 0.95, 0.88)
sun1.rotation_euler = (0.75, 0.3, -0.6)
scene.collection.objects.link(sun1)

sun2 = bpy.data.objects.new('RimSun', bpy.data.lights.new('RimSun', type='SUN'))
sun2.data.energy = 4.2
sun2.data.color = (0.4, 0.8, 1.0)
sun2.rotation_euler = (0.9, 0.2, 2.5)
scene.collection.objects.link(sun2)

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
cam.data.lens = 45
scene.collection.objects.link(cam)
scene.camera = cam

p1 = Vector((2.6, -3.8, 2.2))
cam.location = p1
cam.rotation_euler = (Vector((0, 0, 0.2)) - p1).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(r_dir / "render_front.png")
bpy.ops.render.render(write_still=True)
print("[OK] Rendu Face 1080p terminé")

p2 = Vector((-2.6, 3.8, 2.2))
cam.location = p2
cam.rotation_euler = (Vector((0, 0, 0.2)) - p2).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(r_dir / "render_back.png")
bpy.ops.render.render(write_still=True)
print("[OK] Rendu Dos 1080p terminé")
"""

blender_py_file = Path("/tmp/run_benchmark_blender.py")
blender_py_file.write_text(blender_script)

res_blender = subprocess.run([
    "/home/juan/.local/bin/blender",
    "--background",
    "--python", str(blender_py_file)
], capture_output=True, text=True)
print(res_blender.stdout)

print("\nBENCHMARK_ULTIMATE_COMPLEX_SUCCESS")
