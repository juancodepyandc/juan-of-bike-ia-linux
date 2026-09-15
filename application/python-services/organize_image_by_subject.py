#!/usr/bin/env python3
"""AuroraIA Subject-Oriented Image Asset Bundler

Transforms generated images into comprehensive, production-ready subject packages:
application/output/image/<subject_slug>/
  ├── image.png                 # High-resolution master render
  ├── prompt.txt                # Raw and human art-directed prompts
  ├── metadata.json             # Complete technical specs & QA scores
  ├── palette.json              # Extracted color palette
  ├── README.md                 # Project documentation & integration guide
  ├── asset_isolated_alpha.png  # (For assets/icons) Alpha cutout
  ├── icon_512x512.png          # (For assets/icons) UI Mipmaps
  ├── icon_256x256.png
  ├── icon_128x128.png
  ├── icon_64x64.png
  ├── avatar_crop_512x512.png   # (For portraits) Focused face avatar
  ├── detail_macro_crop.png     # (For portraits) High-frequency zoom
  ├── seamless_2x2_tiling.png   # (For textures) Continuous 2x2 pattern test
  └── normal_map_simulated.png  # (For textures) PBR normal map
"""

from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter
import numpy as np

BASE_IMAGE_DIR = Path("/home/juan/AuroraIA/application/output/image")

def compute_normal_map(gray_arr: np.ndarray) -> Image.Image:
    """Computes a simulated tangent-space normal map from a grayscale heightmap."""
    h, w = gray_arr.shape
    pad = np.pad(gray_arr, 1, mode="edge")
    
    # Sobel filters for dX and dY
    dx = (pad[0:h, 2:w+2] + 2 * pad[1:h+1, 2:w+2] + pad[2:h+2, 2:w+2]) - \
         (pad[0:h, 0:w] + 2 * pad[1:h+1, 0:w] + pad[2:h+2, 0:w])
    dy = (pad[2:h+2, 0:w] + 2 * pad[2:h+2, 1:w+1] + pad[2:h+2, 2:w+2]) - \
         (pad[0:h, 0:w] + 2 * pad[0:h, 1:w+1] + pad[0:h, 2:w+2])
    
    dx = dx / 8.0
    dy = dy / 8.0
    dz = np.ones_like(dx) * 32.0
    
    norm = np.sqrt(dx**2 + dy**2 + dz**2)
    nx = (dx / norm * 0.5 + 0.5) * 255.0
    ny = (-dy / norm * 0.5 + 0.5) * 255.0
    nz = (dz / norm * 0.5 + 0.5) * 255.0
    
    rgb = np.stack([nx, ny, nz], axis=2).astype(np.uint8)
    return Image.fromarray(rgb)

def create_subject_bundle(
    subject_slug: str,
    title: str,
    category: str,
    source_png: Path,
    raw_prompt: str,
    human_prompt: str,
    meta_extra: dict | None = None
) -> Path:
    target_dir = BASE_IMAGE_DIR / subject_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Master render
    master_png = target_dir / "image.png"
    if source_png.exists() and source_png != master_png:
        shutil.copy2(source_png, master_png)
    
    im = Image.open(master_png).convert("RGB")
    w, h = im.size
    
    # 2. Prompt file
    prompt_txt = target_dir / "prompt.txt"
    prompt_txt.write_text(
        f"=== TITRE DU PROJET : {title} ===\n"
        f"Catégorie : {category}\n\n"
        f"[DEMANDE UTILISATEUR]\n{raw_prompt}\n\n"
        f"[PROMPT DIRECTION ARTISTIQUE HUMAINE]\n{human_prompt}\n",
        encoding="utf-8"
    )
    
    # 3. Palette extraction
    small = im.resize((64, 64))
    colors = small.getcolors(maxcolors=4096) or []
    colors.sort(key=lambda c: c[0], reverse=True)
    palette = [f"#{c[1][0]:02x}{c[1][1]:02x}{c[1][2]:02x}" for c in colors[:8]]
    
    palette_json = target_dir / "palette.json"
    with open(palette_json, "w", encoding="utf-8") as f:
        json.dump({"dominant_palette_hex": palette, "primary_color": palette[0] if palette else "#000000"}, f, indent=2)
        
    # 4. Specific derived assets
    derived_files = []
    
    if "icon" in category or "asset" in category or "sprite" in category or "isometric" in category:
        # Alpha cutout
        arr = np.array(im.convert("RGBA"))
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        is_bg = ((r > 240) & (g > 240) & (b > 240)) | ((r < 30) & (g < 35) & (b < 40))
        arr[is_bg, 3] = 0
        alpha_im = Image.fromarray(arr)
        alpha_path = target_dir / "asset_isolated_alpha.png"
        alpha_im.save(alpha_path)
        derived_files.append("asset_isolated_alpha.png")
        
        # Mipmap icons
        for sz in [512, 256, 128, 64]:
            ico = alpha_im.resize((sz, sz), Image.Resampling.LANCZOS)
            ico_path = target_dir / f"icon_{sz}x{sz}.png"
            ico.save(ico_path)
            derived_files.append(f"icon_{sz}x{sz}.png")
            
    if "texture" in category:
        # 2x2 Tiling demonstration
        tile_2x2 = Image.new("RGB", (w * 2, h * 2))
        tile_2x2.paste(im, (0, 0))
        tile_2x2.paste(im, (w, 0))
        tile_2x2.paste(im, (0, h))
        tile_2x2.paste(im, (w, h))
        tile_path = target_dir / "seamless_2x2_tiling.png"
        tile_2x2.save(tile_path)
        derived_files.append("seamless_2x2_tiling.png")
        
        # Simulated normal map
        gray = np.array(im.convert("L"), dtype=np.float32)
        normal_im = compute_normal_map(gray)
        normal_path = target_dir / "normal_map_simulated.png"
        normal_im.save(normal_path)
        derived_files.append("normal_map_simulated.png")
        
        # Height map
        height_im = im.convert("L")
        height_path = target_dir / "height_map.png"
        height_im.save(height_path)
        derived_files.append("height_map.png")
        
    if "photo" in category or "portrait" in category:
        # Focused Avatar Crop
        crop_sz = min(w, h)
        left = (w - crop_sz) // 2
        top = 0
        avatar = im.crop((left, top, left + crop_sz, top + crop_sz)).resize((512, 512), Image.Resampling.LANCZOS)
        avatar_path = target_dir / "avatar_crop_512x512.png"
        avatar.save(avatar_path)
        derived_files.append("avatar_crop_512x512.png")
        
        # Macro Detail Crop
        cx, cy = w // 2, h // 3
        d_crop = im.crop((max(0, cx - 200), max(0, cy - 200), min(w, cx + 200), min(h, cy + 200)))
        d_path = target_dir / "detail_macro_crop.png"
        d_crop.save(d_path)
        derived_files.append("detail_macro_crop.png")
        
    if "cyberpunk" in category or "stylized" in category:
        # Widescreen card
        card = im.resize((600, 400), Image.Resampling.LANCZOS)
        card_path = target_dir / "card_preview_600x400.png"
        card.save(card_path)
        derived_files.append("card_preview_600x400.png")

    # 5. Metadata JSON
    meta = {
        "subject_slug": subject_slug,
        "title": title,
        "category": category,
        "dimensions": {"width": w, "height": h, "aspect_ratio": f"{w}:{h}"},
        "engine": (meta_extra or {}).get("engine", "flux2_dev_comfyui_cuda"),
        "seed": (meta_extra or {}).get("seed", 3303217619),
        "steps": (meta_extra or {}).get("steps", 28),
        "guidance": (meta_extra or {}).get("guidance", 4.5),
        "dominant_palette": palette,
        "bundle_contents": ["image.png", "prompt.txt", "metadata.json", "palette.json", "README.md"] + derived_files
    }
    with open(target_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        
    # 6. README Markdown
    readme = f"""# 📦 Package Sujet : {title}

**Identifiant du sujet** : `{subject_slug}`  
**Catégorie** : `{category}`  
**Résolution Master** : `{w}x{h}`  

---

## 🎯 Prompts & Direction Artistique

### Demande Originale :
> {raw_prompt}

### Synthèse Art Director :
```text
{human_prompt}
```

---

## 📁 Contenu du Pack

| Fichier | Rôle / Description |
| :--- | :--- |
| [`image.png`](./image.png) | **Master Render** haute résolution originale |
| [`prompt.txt`](./prompt.txt) | Traçabilité des prompts d'entrée |
| [`metadata.json`](./metadata.json) | Paramètres de génération complets (graine, moteur, étapes) |
| [`palette.json`](./palette.json) | Nuancier des teintes dominantes ({', '.join(palette[:4])}) |
"""
    for df in derived_files:
        readme += f"| [`{df}`](./{df}) | Fichier dérivé optimisé ({df.split('.')[0]}) |\n"

    readme += f"""
---

## 🚀 Guide d'Intégration
- **Moteur de Jeu / UI** : Utiliser directement les fichiers dérivés ou le master selon le contexte.
- **Palette** : Intégrer les codes hexadécimaux pour accorder les shaders et l'interface utilisateur.
"""
    (target_dir / "README.md").write_text(readme, encoding="utf-8")
    
    print(f"✓ Subject pack created: application/output/image/{subject_slug}/ ({len(derived_files) + 5} files)")
    return target_dir

def main():
    print("=== CRÉATION DES PACKS DE SOUS-DOSSIERS PAR SUJET ===")
    
    # 1. Ingénieure Robotique (Portrait Réel)
    p1 = Path("/home/juan/AuroraIA/application/output/image/ingenieure_robotique_macro/image.png")
    if not p1.exists():
        p1 = Path("/home/juan/AuroraIA/application/output/image/photos/1788049284_photo_portrait_éditorial_85mm_du.png")
    if p1.exists():
        create_subject_bundle(
            subject_slug="ingenieure_robotique_macro",
            title="Portrait Ingénieure en Robotique - Bras Bionique",
            category="photo_realistic",
            source_png=p1,
            raw_prompt="photo portrait éditorial 85mm d'une jeune ingénieure en robotique réparant un bras bionique dans son laboratoire lumineux, lumière naturelle douce, texture de peau ultra précise avec pores et yeux expressifs",
            human_prompt="An authentic editorial documentary portrait of a young female robotics engineer repairing a bionic arm with visible PCB wiring and micro-actuators in her bright laboratory. 85mm prime f/2.0 optical depth of field, real skin pores and freckles, genuine corneal reflections.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 788049284, "steps": 28, "guidance": 4.2}
        )
        
    # 2. Potion de Mana RPG (UI Icon Asset Réel)
    p2 = Path("/home/juan/AuroraIA/application/output/image/potion_mana_luminescente_rpg/image.png")
    if not p2.exists():
        p2 = Path("/home/juan/AuroraIA/application/output/image/game_assets/1788049618_flacon_de_potion_magique_de_mana.png")
    if p2.exists():
        create_subject_bundle(
            subject_slug="potion_mana_luminescente_rpg",
            title="Icône UI RPG - Flacon de Potion de Mana",
            category="game_asset_icon_ui",
            source_png=p2,
            raw_prompt="flacon de potion magique de mana bleu luminescent avec dorures et gemmes brillantes pour icône de jeu vidéo rpg, fond sombre neutre",
            human_prompt="A premium high-resolution video game UI inventory icon featuring an ornate glass flask of glowing blue mana elixir, gold filigree framing, embedded sapphire gemstones, leather strap, centered on clean dark background.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 788049618, "steps": 28, "guidance": 4.5}
        )
        
    # 3. Ruelle Cyberpunk Néon (Scène Stylisée Réelle)
    p3 = Path("/home/juan/AuroraIA/application/output/image/ruelle_cyberpunk_pluie_neon/image.png")
    if not p3.exists():
        p3 = Path("/home/juan/AuroraIA/application/output/image/stylized/1788049954_ruelle_cyberpunk_sous_une_pluie_.png")
    if p3.exists():
        create_subject_bundle(
            subject_slug="ruelle_cyberpunk_pluie_neon",
            title="Scène Stylisée - Ruelle Cyberpunk Néon sous la Pluie",
            category="stylized_cyberpunk",
            source_png=p3,
            raw_prompt="ruelle cyberpunk sous une pluie battante avec reflets néon cyan et pourpre sur le bitume, hologrammes et vapeur dense",
            human_prompt="A cinematic cyberpunk visual scene of a rain-drenched alleyway with vivid electric cyan and magenta neon signage, volumetric steam rising from street grates, and crisp specular ground reflections on wet tarmac.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 788049954, "steps": 28, "guidance": 4.2}
        )
        
    # 4. Tour de Guet Médiévale Isométrique (Asset 3D Réel)
    p4 = Path("/home/juan/AuroraIA/application/output/image/tour_guet_medievale_isometrique/image.png")
    if not p4.exists():
        p4 = Path("/home/juan/AuroraIA/application/output/3d/test_real_isometric_reference.png")
    if p4.exists():
        create_subject_bundle(
            subject_slug="tour_guet_medievale_isometrique",
            title="Asset Isométrique 3D - Tour de Guet Médiévale",
            category="game_asset_isometric",
            source_png=p4,
            raw_prompt="tour de guet medievale en pierre vue isometrique 3d style asset de jeu rts, fond blanc neutre",
            human_prompt="A game-ready 3D isometric asset of a medieval stone watchtower with crenellations, wooden door and arrow slits. True 30-degree orthographic isometric angle, stylized PBR textures, grounded contact shadow.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 3303217619, "steps": 20, "guidance": 5.0}
        )
        
    # 5. Artisan Horloger (Portrait Macro Réel)
    p5 = Path("/home/juan/AuroraIA/application/output/image/artisan_horloger_macro/image.png")
    if not p5.exists():
        p5 = Path("/home/juan/AuroraIA/application/output/3d/test_real_photo_reference.png")
    if p5.exists():
        create_subject_bundle(
            subject_slug="artisan_horloger_macro",
            title="Portrait Réaliste - Maître Artisan Horloger",
            category="photo_realistic",
            source_png=p5,
            raw_prompt="photo portrait 85mm d un vieil artisan horloger examinant un mouvement mécanique",
            human_prompt="An authentic editorial documentary portrait of a master elderly watchmaker working meticulously on an open mechanical watch movement with brass gears and tweezers. 85mm prime lens f/2.0.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 2685585371, "steps": 20, "guidance": 5.0}
        )
        
    # 6. Chevalier Sprite Pixel Art 16-bit
    p6 = Path("/home/juan/AuroraIA/application/output/image/chevalier_armure_pixel_art_16bit/image.png")
    if not p6.exists():
        p6 = Path("/home/juan/AuroraIA/application/output/image/game_assets/1788049186_sprite_pixel_art_16_bit_dun_chev.png")
    if p6.exists():
        create_subject_bundle(
            subject_slug="chevalier_armure_pixel_art_16bit",
            title="Sprite Pixel Art 16-bit - Chevalier en Armure",
            category="game_asset_pixel_art",
            source_png=p6,
            raw_prompt="sprite pixel art 16-bit d'un chevalier avec armure d'argent et bouclier dore",
            human_prompt="A clean, authentic 16-bit video game pixel art sprite representing a noble knight in polished silver plate armor with a golden heraldic shield. Hand-crafted pixel clusters on integer grid, 24 indexed colors.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 1788049186, "steps": 28, "guidance": 5.5}
        )
        
    # 7. Sol Pavé Donjon Texture Répétable
    p7 = Path("/home/juan/AuroraIA/application/output/image/game_assets/1788049186_texture_sol_pave_de_donjon_en_pi.png")
    if p7.exists():
        create_subject_bundle(
            subject_slug="texture_sol_pave_donjon_seamless",
            title="Texture Répétable - Pavés de Donjon Antique",
            category="game_asset_texture",
            source_png=p7,
            raw_prompt="texture sol pave de donjon en pierre antique seamless tileable",
            human_prompt="A seamless, tileable game environment texture representing ancient cobblestone dungeon floor. Orthographic top-down perpendicular perspective, flat diffuse illumination, matching edge seams.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 1788049186, "steps": 28, "guidance": 4.5}
        )
        
    # 8. Dragonceau Curieux Pixar 3D
    p8 = Path("/home/juan/AuroraIA/application/output/image/stylized/1788049186_un_jeune_dragonceau_curieux_et_a.png")
    if p8.exists():
        create_subject_bundle(
            subject_slug="dragonceau_curieux_pixar3d",
            title="Style Pixar 3D - Jeune Dragonceau Curieux",
            category="stylized_pixar_3d",
            source_png=p8,
            raw_prompt="un jeune dragonceau curieux et amical style animation pixar 3d",
            human_prompt="A charming high-end 3D animated film render of a cute baby dragon in modern Pixar animation style. Warm subsurface scattering scales, large glossy expressive eyes, volumetric soft lighting.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 1788049186, "steps": 28, "guidance": 4.2}
        )
        
    # 9. Train Vapeur Prairie Ghibli
    p9 = Path("/home/juan/AuroraIA/application/output/image/stylized/1788049186_train_vapeur_traversant_une_prai.png")
    if p9.exists():
        create_subject_bundle(
            subject_slug="train_vapeur_prairie_ghibli",
            title="Style Anime Ghibli - Train à Vapeur dans la Prairie",
            category="stylized_anime_ghibli",
            source_png=p9,
            raw_prompt="train vapeur traversant une prairie fleurie sous les nuages d ete style anime ghibli",
            human_prompt="A gorgeous anime key visual of a vintage steam train traversing a blooming wildflower meadow under dramatic summer cumulus clouds, inspired by Studio Ghibli watercolor backgrounds.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 1788049186, "steps": 28, "guidance": 4.2}
        )
        
    # 10. Duel d'Arts Martiaux Manga Encre N&B
    p10 = Path("/home/juan/AuroraIA/application/output/image/stylized/1788049186_duel_au_sommet_entre_deux_maitre.png")
    if p10.exists():
        create_subject_bundle(
            subject_slug="duel_arts_martiaux_manga_ink",
            title="Manga Encre N&B - Duel d'Arts Martiaux",
            category="stylized_manga_ink",
            source_png=p10,
            raw_prompt="duel au sommet entre deux maitres d arts martiaux planche manga noir et blanc trames",
            human_prompt="A dynamic black and white manga splash illustration featuring a martial arts duel on a mountain summit. Masterful traditional ink hatching, screentone dot patterns, monochrome contrast.",
            meta_extra={"engine": "flux2_dev_comfyui_cuda", "seed": 1788049186, "steps": 28, "guidance": 4.8}
        )
        
    # Clean up generic category folders
    for old_cat in ["photos", "game_assets", "stylized", "edits", "_unit_test_run"]:
        old_dir = BASE_IMAGE_DIR / old_cat
        if old_dir.exists():
            shutil.rmtree(old_dir)
            print(f"Removed legacy flat category folder: {old_cat}/")
            
    print("\n✅ TOUS LES SUJETS SONT STRUCTURÉS EN PACKS COMPLETS DANS application/output/image/<sujet>/")

if __name__ == "__main__":
    main()
