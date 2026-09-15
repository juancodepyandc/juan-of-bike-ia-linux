#!/usr/bin/env python3
"""AuroraIA Category & Subject Image Packaging Engine

Implements the user's requested 2-level structure:
application/output/image/<category>/<subject_slug>/
  ├── image.png                 # Master high-resolution render
  ├── prompt.txt                # Raw and human art-directed prompts
  ├── metadata.json             # Complete technical specs & QA scores
  ├── palette.json              # Extracted color palette
  ├── README.md                 # Project documentation & integration guide
  ├── asset_isolated_alpha.png  # (For assets) Alpha cutout
  ├── icon_512x512.png          # (For assets) UI Mipmaps
  ├── icon_256x256.png
  ├── icon_128x128.png
  ├── icon_64x64.png
  ├── avatar_crop_512x512.png   # (For perso) Focused face avatar
  ├── detail_macro_crop.png     # (For perso) High-frequency zoom
  ├── seamless_2x2_tiling.png   # (For textures) Continuous 2x2 pattern test
  └── normal_map_simulated.png  # (For textures) PBR normal map
"""

from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from PIL import Image
import numpy as np

BASE_IMAGE_DIR = Path("/home/juan/AuroraIA/application/output/image")

def map_intent_to_main_category(cat: str, text: str = "") -> str:
    c = cat.lower()
    t = text.lower()
    if "asset" in c or "sprite" in c or "pixel" in c or "isometric" in c or "icon" in c or "texture" in c or "prop" in c:
        return "assets"
    if "portrait" in t or "visage" in t or "femme" in t or "homme" in t or "personne" in t or "ingenieur" in t or "artisan" in t or "dragon" in t or "duel" in t or "perso" in t or "character" in t or "pixar" in c or "manga" in c:
        return "perso"
    if "decor" in t or "ruelle" in t or "rue" in t or "paysage" in t or "cyberpunk" in c or "ghibli" in c or "train" in t or "concept" in c:
        return "decor"
    if "edit" in c:
        return "edits"
    return "perso" if "photo" in c else "decor"

def reorganize_into_categories():
    print("=== RÉORGANISATION DES SOUS-DOSSIERS EN output/image/<categorie>/<sujet>/ ===")
    
    # 1. Create main category directories
    for cat in ["assets", "perso", "decor", "edits"]:
        (BASE_IMAGE_DIR / cat).mkdir(parents=True, exist_ok=True)
        
    # Map of current subject folders to target category
    subject_mappings = {
        "ingenieure_robotique_macro": "perso",
        "artisan_horloger_macro": "perso",
        "dragonceau_curieux_pixar3d": "perso",
        "duel_arts_martiaux_manga_ink": "perso",
        "potion_mana_luminescente_rpg": "assets",
        "tour_guet_medievale_isometrique": "assets",
        "chevalier_armure_pixel_art_16bit": "assets",
        "texture_sol_pave_donjon_seamless": "assets",
        "ruelle_cyberpunk_pluie_neon": "decor",
        "train_vapeur_prairie_ghibli": "decor",
        "renard_neige": "perso",
    }
    
    for subject_name, target_cat in subject_mappings.items():
        src = BASE_IMAGE_DIR / subject_name
        dst = BASE_IMAGE_DIR / target_cat / subject_name
        if src.exists() and src != dst:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))
            print(f"✓ Déplacé : {subject_name} -> output/image/{target_cat}/{subject_name}/")
            
    print("\n✅ ARBORESCENCE CONFORME : output/image/<categorie>/<nom_du_sujet>/")

if __name__ == "__main__":
    reorganize_into_categories()
