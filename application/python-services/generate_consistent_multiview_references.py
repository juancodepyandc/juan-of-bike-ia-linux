#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_consistent_multiview_references.py — Générateur Multi-Vues Cohérent SOTA (MV-Adapter SDXL) :
Génère 6 vues orthographiques rigoureusement identiques et cohérentes (Face, Profil Droit, Dos, Profil Gauche)
depuis une image de référence unique avec le modèle MV-Adapter.
"""
import os
import sys
import torch
from pathlib import Path
from PIL import Image

sys.path.insert(0, "/home/juan/.local/share/auroraia/external/MV-Adapter")

from mvadapter.pipelines.pipeline_mvadapter_i2mv_sdxl import MVAdapterI2MVSDXLPipeline
from mvadapter.schedulers.scheduling_shift_snr import ShiftSNRScheduler
from mvadapter.utils.mesh_utils import get_orthogonal_camera
from mvadapter.utils.geometry import get_plucker_embeds_from_cameras_ortho
from mvadapter.utils import make_image_grid
from transformers import AutoModelForImageSegmentation
from torchvision import transforms

PROJECT_DIR = Path("/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall")
REFS_DIR = PROJECT_DIR / "references"
INPUT_IMG_PATH = REFS_DIR / "master_concept.png"

print(f"Chargement de MV-Adapter SDXL sur CUDA...")
base_model = "stabilityai/stable-diffusion-xl-base-1.0"
adapter_path = "huanngzh/mv-adapter"
device = "cuda"
dtype = torch.float16

pipe = MVAdapterI2MVSDXLPipeline.from_pretrained(
    base_model,
    torch_dtype=dtype,
    variant="fp16"
)
pipe.scheduler = ShiftSNRScheduler.from_scheduler(
    pipe.scheduler,
    shift_mode="interpolated",
    shift_scale=8.0
)
pipe.init_custom_adapter(num_views=6)
pipe.load_custom_adapter(
    adapter_path,
    weight_name="mvadapter_i2mv_sdxl.safetensors"
)
pipe.to(device=device, dtype=dtype)
pipe.cond_encoder.to(device=device, dtype=dtype)

# Charger BiRefNet pour détourage propre
birefnet = AutoModelForImageSegmentation.from_pretrained(
    "ZhengPeng7/BiRefNet",
    trust_remote_code=True
).to(device=device, dtype=dtype)
birefnet.eval()

# Charger et préparer l'image d'entrée
input_img = Image.open(str(INPUT_IMG_PATH)).convert("RGB")

# Masque de premier plan
transform_image = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
input_tensor = transform_image(input_img).unsqueeze(0).to(device=device, dtype=dtype)
with torch.no_grad():
    preds = birefnet(input_tensor)[-1].sigmoid().cpu()
pred = preds[0].squeeze()
mask = transforms.ToPILImage()(pred).resize(input_img.size)

# Créer image avec fond blanc pur
input_nobg = Image.new("RGB", input_img.size, (255, 255, 255))
input_nobg.paste(input_img, mask=mask)
input_nobg = input_nobg.resize((768, 768))

# Caméras 6 vues orthographiques : [0, 60, 120, 180, 240, 300]
cameras = get_orthogonal_camera(
    elevation_deg=[0, 0, 0, 0, 0, 0],
    distance=[1.8]*6,
    left=-0.55, right=0.55, bottom=-0.55, top=0.55,
    azimuth_deg=[0, 60, 120, 180, 240, 300],
    device=device
)
plucker_embeds = get_plucker_embeds_from_cameras_ortho(cameras, 768).to(device=device, dtype=dtype)

print("Génération des 6 vues strictement cohérentes...")
generator = torch.Generator(device=device).manual_seed(777)
with torch.no_grad():
    images = pipe(
        image=input_nobg,
        prompt="masterpiece, best quality, ultra-detailed, fairy tail guild hall building, consistent anime architecture",
        negative_prompt="blurry, distorted, low quality, deformed, inconsistent",
        num_views=6,
        camera_embedding=plucker_embeds,
        height=768,
        width=768,
        num_inference_steps=30,
        guidance_scale=5.0,
        generator=generator
    ).images[0]

# Sauvegarder les 6 vues dans references/
view_names = [
    "view_01_front.png",
    "view_02_front_right.png",
    "view_03_back_right.png",
    "view_04_back.png",
    "view_05_back_left.png",
    "view_06_front_left.png"
]

for img, name in zip(images, view_names):
    out_path = REFS_DIR / name
    img.save(str(out_path))
    print(f"  [OK] Vue sauvegardée : {name}")

# Sauvegarder également la planche complète Turnaround 6 vues
grid_img = make_image_grid(images, rows=2, cols=3)
turnaround_sheet_path = REFS_DIR / "turnaround_6_views_sheet.png"
grid_img.save(str(turnaround_sheet_path))
print(f"[OK] Planche Turnaround 6 vues cohérentes sauvegardée : {turnaround_sheet_path}")

print("MVADAPTER_GENERATION_SUCCESS")
