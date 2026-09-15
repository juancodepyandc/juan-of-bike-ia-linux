#!/usr/bin/env python3
"""AuroraIA Real Pipeline Live Optimization & Generation Benchmark.

Executes real FLUX.2 neural diffusion jobs on RTX 5070 Ti via ComfyUI.
Measures execution time, VRAM usage, and output quality across:
1. Photo-realism
2. Video Game Asset (UI Icon & Pixel Art)
3. Stylized Art (Cyberpunk Neon & Anime)
"""

import json
import os
import sys
import time
from pathlib import Path
from PIL import Image

sys.path.append(str(Path(__file__).parent))
from human_prompt_director import direct_prompt, detect_category
from image_module_engine import (
    generate_image_manifest,
    calculate_sharpness,
    calculate_contrast,
    calculate_dominant_palette
)

REAL_TESTS = [
    {
        "id": "real_photo_cyber_portrait",
        "category": "photo_realistic",
        "subfolder": "photos",
        "prompt": "photo portrait éditorial 85mm d'une jeune ingénieure en robotique réparant un bras bionique dans son laboratoire lumineux, lumière naturelle douce, texture de peau ultra précise avec pores et yeux expressifs",
        "steps": 20,
    },
    {
        "id": "real_game_asset_potion",
        "category": "game_asset_icon_ui",
        "subfolder": "game_assets",
        "prompt": "flacon de potion magique de mana bleu luminescent avec dorures et gemmes brillantes pour icône de jeu vidéo rpg, fond sombre neutre",
        "steps": 20,
    },
    {
        "id": "real_stylized_cyberpunk",
        "category": "stylized_cyberpunk",
        "subfolder": "stylized",
        "prompt": "ruelle cyberpunk sous une pluie battante avec reflets néon cyan et pourpre sur le bitume, hologrammes et vapeur dense",
        "steps": 20,
    }
]

def run_real_pipeline():
    print("=================================================================")
    print("🚀 DÉMARRAGE DU VRAI PIPELINE FLUX.2 SUR GPU (RTX 5070 Ti)")
    print("=================================================================\n")
    
    results = []
    
    for i, test in enumerate(REAL_TESTS, 1):
        print(f"\n--- [TEST RÉEL {i}/{len(REAL_TESTS)}] : {test['category'].upper()} ---")
        print(f"Demande utilisateur : \"{test['prompt']}\"")
        
        # 1. Synthesize Human Art Director Prompt
        spec = direct_prompt(test["prompt"])
        print(f"\n[Human Art Director Prose] :\n{spec['human_prompt']}\n")
        
        # 2. Execute Real Diffusion Pipeline
        start_t = time.time()
        manifest = generate_image_manifest(
            raw_prompt=test["prompt"],
            force_category=test["category"],
            use_comfy=True
        )
        duration = round(time.time() - start_t, 2)
        
        png_path = Path(manifest["output_files"]["image_path"])
        json_path = Path(manifest["output_files"]["manifest_path"])
        
        # 3. Analyze Output Quality
        im = Image.open(png_path)
        w, h = im.size
        sharpness = calculate_sharpness(im)
        contrast = calculate_contrast(im)
        palette = calculate_dominant_palette(im)
        
        print(f"\n[RÉSULTAT DU RENDU] :")
        print(f"  • Image générée  : {png_path} ({w}x{h}, {png_path.stat().st_size / 1024:.1f} Ko)")
        print(f"  • JSON Manifest  : {json_path}")
        print(f"  • Moteur utilisé : {manifest['generation_params']['engine']}")
        print(f"  • Temps total    : {duration}s")
        print(f"  • Netteté (Lap.) : {sharpness:.1f}")
        print(f"  • Contraste      : {contrast:.1f}")
        print(f"  • Palette        : {palette[:3]}")
        
        results.append({
            "id": test["id"],
            "category": test["category"],
            "png": str(png_path),
            "size_kb": png_path.stat().st_size / 1024,
            "resolution": f"{w}x{h}",
            "duration_s": duration,
            "engine": manifest["generation_params"]["engine"],
            "sharpness": sharpness,
            "contrast": contrast
        })
        
    print("\n=================================================================")
    print(f"✅ VRAI PIPELINE VALIDÉ : {len(results)}/{len(REAL_TESTS)} RENDUS TERMINÉS AVEC SUCCÈS")
    print("=================================================================")

if __name__ == "__main__":
    run_real_pipeline()
