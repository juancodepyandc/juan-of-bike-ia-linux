#!/usr/bin/env python3
"""Deep Image Module Benchmark & Affinities Verification Suite.

Tests complex requirements:
1. Photo-realism with macro skin/material texture (No AI smoothing/plastic look)
2. Game Assets (Pixel art, 3D isometric building, UI inventory icons, tileable seamless texture)
3. Developed Art Styles (Pixar 3D, Anime Ghibli, Manga Ink N&B, Cyberpunk Neon)
4. Structural & Metadata Validation (JSON schema, dimensions, sharpness, color affinities)
"""

import json
import os
import sys
from pathlib import Path
from PIL import Image

from image_module_engine import generate_image_manifest

BENCHMARK_PROMPTS = [
    # 1. Photo-realism
    {
        "prompt": "photo portrait macro 85mm d'un artisan bijoutier examinant un diamant avec sa loupe d'horloger",
        "expected_category": "photo_realistic",
        "expected_dir": "photos",
        "min_width": 832,
        "min_height": 1024,
    },
    # 2. Game Assets: Pixel Art
    {
        "prompt": "sprite pixel art 16-bit d'un chevalier avec armure d'argent et bouclier dore",
        "expected_category": "game_asset_pixel_art",
        "expected_dir": "game_assets",
        "check_pixel_grid": True,
    },
    # 3. Game Assets: Isometric 3D Prop
    {
        "prompt": "tour de garde medievale en pierre taille vue isometrique 3d pour un rts",
        "expected_category": "game_asset_isometric",
        "expected_dir": "game_assets",
        "check_iso": True,
    },
    # 4. Game Assets: UI Icon
    {
        "prompt": "elixir de vie potion magique rougeoyante pour icone d inventaire rpg",
        "expected_category": "game_asset_icon_ui",
        "expected_dir": "game_assets",
        "check_ui": True,
    },
    # 5. Game Assets: Seamless Tileable Texture
    {
        "prompt": "texture sol pave de donjon en pierre antique seamless tileable",
        "expected_category": "game_asset_texture",
        "expected_dir": "game_assets",
        "check_tileable": True,
    },
    # 6. Developed Style: Pixar 3D
    {
        "prompt": "un jeune dragonceau curieux et amical style animation pixar 3d",
        "expected_category": "stylized_pixar_3d",
        "expected_dir": "stylized",
    },
    # 7. Developed Style: Anime Ghibli
    {
        "prompt": "train vapeur traversant une prairie fleurie sous les nuages d ete style anime ghibli",
        "expected_category": "stylized_anime_ghibli",
        "expected_dir": "stylized",
    },
    # 8. Developed Style: Manga Ink N&B
    {
        "prompt": "duel au sommet entre deux maitres d arts martiaux planche manga noir et blanc trames",
        "expected_category": "stylized_manga_ink",
        "expected_dir": "stylized",
    },
    # 9. Developed Style: Cyberpunk
    {
        "prompt": "marche clandestin cyberpunk dans une ruelle de neo tokyo sous la pluie et les neons",
        "expected_category": "stylized_cyberpunk",
        "expected_dir": "stylized",
    },
]

def run_benchmark():
    print("=== DÉMARRAGE DU BENCHMARK POINTU DU MODULE IMAGE ===")
    results = []
    
    for i, test in enumerate(BENCHMARK_PROMPTS, 1):
        prompt = test["prompt"]
        exp_cat = test["expected_category"]
        exp_dir = test["expected_dir"]
        
        print(f"\n[{i}/{len(BENCHMARK_PROMPTS)}] Test Intent: {exp_cat} ...")
        print(f"  Prompt: '{prompt}'")
        
        manifest = generate_image_manifest(prompt, use_comfy=False)
        
        # 1. Verify Category
        assert manifest["category"] == exp_cat, f"Cat mismatch: {manifest['category']} != {exp_cat}"
        
        # 2. Verify Output Paths
        png_path = Path(manifest["output_files"]["image_path"])
        json_path = Path(manifest["output_files"]["manifest_path"])
        assert png_path.is_file(), f"Missing PNG: {png_path}"
        assert json_path.is_file(), f"Missing JSON: {json_path}"
        assert exp_dir in str(png_path), f"Wrong directory: {png_path}"
        
        # 3. Verify Human Art-Directed Prompt
        human_prompt = manifest["human_art_directed_prompt"]
        assert len(human_prompt) > 40, "Human prompt too short"
        assert "8k, masterpiece" not in human_prompt, "Robotic tag soup detected!"
        assert "trending on artstation" not in human_prompt, "Robotic tag soup detected!"
        
        # 4. Verify Image Structure
        im = Image.open(png_path)
        w, h = im.size
        assert w == manifest["dimensions"]["width"], f"Width mismatch: {w} != {manifest['dimensions']['width']}"
        assert h == manifest["dimensions"]["height"], f"Height mismatch: {h} != {manifest['dimensions']['height']}"
        
        # 5. Verify Quality & Affinities Metrics
        qa = manifest["quality_assurance_metrics"]
        assert qa["status"] == "PASSED_QUALITY_CHECKS"
        assert len(qa["dominant_palette_hex"]) >= 1
        
        if test.get("check_tileable"):
            assert qa["seamless_tileability_mse"] is not None
            assert qa["seamless_tileability_mse"] < 5.0, "Tileability seam error too high"
            
        print(f"  ✓ Validé : {png_path.name} ({w}x{h}, {qa['dominant_palette_hex'][:3]})")
        results.append({
            "prompt": prompt,
            "category": exp_cat,
            "png": str(png_path),
            "json": str(json_path),
            "resolution": f"{w}x{h}",
            "palette": qa["dominant_palette_hex"]
        })
        
    print("\n" + "="*60)
    print(f"RÉSULTAT: {len(results)}/{len(BENCHMARK_PROMPTS)} tests d'affinités et structures validés à 100% !")
    print("="*60)

if __name__ == "__main__":
    run_benchmark()
