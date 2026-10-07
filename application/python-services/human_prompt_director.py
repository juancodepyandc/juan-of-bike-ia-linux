#!/usr/bin/env python3
"""AuroraIA Human Prompt Director (Python Backend)

Generates evocative, art-directed natural language prompts for:
- High-fidelity Photo-realism
- Video Game Assets (Pixel art, 3D isometric props, UI icons, Tileable textures)
- Stylized art (Pixar 3D, Anime/Ghibli, Manga ink, Cyberpunk, Oil painting, Watercolor)
- Production Concept Art

Eliminates robotic tag stuffing in favor of coherent artistic prose.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional
import unicodedata

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def detect_category(raw_text: str) -> str:
    text = strip_accents(raw_text.lower())
    
    # 1. Game Assets - Specific patterns
    if re.search(r"\b(pixel art|pixelart|pixel-art|sprite|spritesheet|tileset|8.?bit|16.?bit|aseprite|rpg maker|gameboy|snes|nes)\b", text):
        return "game_asset_pixel_art"
    if re.search(r"\b(isometrique|isometric|iso prop|iso building|diorama|simcity|diablo view)\b", text):
        return "game_asset_isometric"
    if re.search(r"\b(icone|icon|item|potion|inventory|loot|competence|skill icon|hud|ui asset|inventaire|badge)\b", text):
        return "game_asset_icon_ui"
    # Tileable texture (excluding organic skin/hair/cloth textures)
    if re.search(r"\b(seamless|tileable|motif repetable|sol carrelage|pbr texture|albedo map|texture de sol|texture de mur|texture 3d repetable)\b", text):
        return "game_asset_texture"
    if re.search(r"\b(texture)\b", text) and not re.search(r"\b(texture de peau|skin texture|texture du visage|texture des cheveux|texture du tissu)\b", text) and re.search(r"\b(sol|mur|pave|pierre|bois|metal|pbr|seamless|tile)\b", text):
        return "game_asset_texture"
    if re.search(r"\b(asset 3d|game prop|low poly prop|game asset|asset jeu|modele pour jeu)\b", text):
        return "game_asset_3d_prop"
        
    # 2. Stylized & Animation
    if re.search(r"\b(pixar|disney|animation 3d|dreamworks|personnage 3d stylise|caricature 3d)\b", text):
        return "stylized_pixar_3d"
    if re.search(r"\b(anime|ghibli|shinkai|makoto|cel.?shad|cleankey|japonais animation|dessin anime)\b", text):
        return "stylized_anime_ghibli"
    if re.search(r"\b(manga|noir et blanc|encre|screentone|trame|planche manga|shonen|seinen)\b", text):
        return "stylized_manga_ink"
    if re.search(r"\b(cyberpunk|neon noir|futuriste neon|blade runner|synthwave)\b", text):
        return "stylized_cyberpunk"
    if re.search(r"\b(huile|oil painting|peinture a l huile|toile de maitre|caravaggio|rembrandt)\b", text):
        return "stylized_oil_painting"
    if re.search(r"\b(aquarelle|watercolor|lavis|papier grain)\b", text):
        return "stylized_watercolor"
    if re.search(r"\b(concept art|matte painting|production art|decor epique|cle visual)\b", text):
        return "concept_art_production"
        
    # 3. Photo-Realistic default
    return "photo_realistic"

def _style_prompt(raw_input: str, cat: str) -> Dict[str, Any]:
    subj = raw_input.strip(" ,.-;")
    
    if cat == "photo_realistic":
        is_portrait = bool(re.search(r"\b(portrait|visage|femme|homme|personne|regard|fille|garcon|ingenieure?|artisan|docteur|modele|chef)\b", subj, re.I))
        is_landscape = bool(re.search(r"\b(paysage|montagne|foret|mer|plage|ciel|horizon|ville|rue)\b", subj, re.I))
        
        w, h = (832, 1216) if is_portrait else ((1216, 832) if is_landscape else (1024, 1024))
        ar = "2:3" if is_portrait else ("3:2" if is_landscape else "1:1")
        
        if is_portrait:
            prompt = (f"An authentic editorial documentary portrait of {subj}. Natural daylight illumination with soft "
                      "directional shadows that accentuate real skin texture, fine pores, subtle natural imperfections, and "
                      "expressive eyes with clear corneal reflections. Captured on an 85mm prime lens at f/2.0 with a gentle shallow "
                      "depth of field, delicate optical bokeh in the background, and true-to-life color fidelity. No artificial "
                      "airbrushing, no plastic skin smoothing, genuine human presence.")
        else:
            prompt = (f"A genuine documentary-grade photograph capturing {subj}. Natural atmospheric lighting with believable "
                      "specular highlights, authentic surface textures, and physical contact shadows. Shot with professional 35mm "
                      "optical glass, capturing realistic depth, tactile material micro-textures, and organic tonal gradients "
                      "without oversaturation or synthetic HDR effects.")
            
        return {
            "category": "photo_realistic",
            "title": f"Photographie Réaliste - {subj[:32]}",
            "human_prompt": prompt,
            "negative_prompt": "plastic skin, airbrushed, cartoon, 3d render, CGI, doll face, fake smooth texture, oversaturated, unnatural glow, extra limbs, deformed anatomy, blurry, low resolution, watermark, signature",
            "aspect_ratio": ar,
            "width": w,
            "height": h,
            "steps": 50,
            "guidance": 4.2,
            "suggested_directory": "photos",
            "quality_checklist": [
                "Texture de peau et matières organiques naturelles",
                "Éclairage cohérent avec ombres de contact physiques",
                "Aucun lissage plastique ni effet filtre IA",
                "Profondeur optique réaliste (bokeh naturel)"
            ]
        }
        
    elif cat == "game_asset_pixel_art":
        return {
            "category": "game_asset_pixel_art",
            "title": f"Pixel Art Sprite - {subj[:32]}",
            "human_prompt": (f"A clean, authentic 16-bit video game pixel art sprite representing {subj}. Hand-crafted pixel clusters "
                             "on a strict integer grid, readable silhouette, limited indexed color palette (16 to 32 colors max), "
                             "crisp 1-pixel outlines, and deliberate dithering on shadows. Isolated on a clean solid neutral background "
                             "for seamless sprite cutting and game engine integration. No subpixel blurring, no anti-aliased gradients, "
                             "pure retro gaming aesthetic."),
            "negative_prompt": "anti-aliasing, vector smoothing, 3d render, photorealistic, blurred pixels, soft gradients, messy noise, watermark",
            "aspect_ratio": "1:1",
            "width": 1024,
            "height": 1024,
            "steps": 50,
            "guidance": 5.5,
            "game_asset_meta": {
                "asset_type": "sprite",
                "isolated_background": True,
                "grid_size": 32,
                "pixel_scale": 4
            },
            "suggested_directory": "game_assets",
            "quality_checklist": [
                "Grille de pixels entière et nette",
                "Palette de couleurs indexée rétro",
                "Silhouette immédiatement lisible en jeu",
                "Fond neutre isolé prêt à détourer"
            ]
        }
        
    elif cat == "game_asset_isometric":
        return {
            "category": "game_asset_isometric",
            "title": f"Asset Isométrique - {subj[:32]}",
            "human_prompt": (f"A game-ready 3D isometric asset of {subj}, designed for an RTS or tactical RPG game. True 30-degree "
                             "orthographic isometric angle, stylized hand-painted PBR textures, clean readable geometric volumes, "
                             "and clear directional key lighting casting a soft grounded contact shadow. Centered in frame and isolated "
                             "on a solid neutral backdrop with generous margins for easy game sprite extraction."),
            "negative_prompt": "perspective distortion, wide angle lens, fish eye, cut off edges, cluttered background, realistic photo, motion blur, watermark",
            "aspect_ratio": "1:1",
            "width": 1024,
            "height": 1024,
            "steps": 50,
            "guidance": 4.8,
            "game_asset_meta": {
                "asset_type": "isometric_building",
                "isolated_background": True
            },
            "suggested_directory": "game_assets",
            "quality_checklist": [
                "Angle orthographique isométrique 30° strict",
                "Silhouette propre et volumes lisibles",
                "Ombre portée au sol cohérente",
                "Sujet centré et isolé sans coupure"
            ]
        }

    elif cat == "game_asset_3d_prop":
        return {
            "category": cat, "title": f"Asset 3D - {subj[:32]}",
            "human_prompt": f"A detailed game prop render of {subj}. Clear readable geometry, coherent materials and clean contours. Preserve the requested view and setting.",
            "negative_prompt": "blurry, cut off edges, watermark, deformed geometry",
            "aspect_ratio": "1:1", "width": 1024, "height": 1024,
            "steps": 50, "guidance": 4.5, "suggested_directory": "game_assets",
            "game_asset_meta": {"asset_type": "3d_prop"},
            "quality_checklist": ["Géométrie et matières lisibles", "Vue et sujet conformes à la demande"],
        }

    elif cat == "game_asset_icon_ui":
        return {
            "category": "game_asset_icon_ui",
            "title": f"Icône de Jeu - {subj[:32]}",
            "human_prompt": (f"A premium high-resolution video game UI inventory icon featuring {subj}. Centered, floating slightly in "
                             "perspective, with bold iconic silhouette, rich stylized materials (polished metal, glowing gems, or weathered "
                             "leather), vibrant accent edge rim-lighting, and crisp defined contours. Isolated against a clean dark slate "
                             "backdrop, optimized for RPG inventory slots and HUD action bars."),
            "negative_prompt": "photograph, cluttered scene, low contrast, cropped borders, blurry edges, extra items, text, numbers, watermark",
            "aspect_ratio": "1:1",
            "width": 1024,
            "height": 1024,
            "steps": 50,
            "guidance": 4.5,
            "game_asset_meta": {
                "asset_type": "ui_icon",
                "isolated_background": True
            },
            "suggested_directory": "game_assets",
            "quality_checklist": [
                "Cadrage centré d'icône avec marges",
                "Matières et reflets contrastés pour lisibilité en petite taille",
                "Fond uniforme prêt pour intégration UI",
                "Zéro artefact ou texte parasite"
            ]
        }

    elif cat == "game_asset_texture":
        return {
            "category": "game_asset_texture",
            "title": f"Texture Répétable - {subj[:32]}",
            "human_prompt": (f"A seamless, tileable game environment texture representing {subj}. Orthographic top-down perpendicular "
                             "perspective, completely flat even diffuse illumination without cast shadows or vignettes, consistent tactile "
                             "surface details (roughness, grain, crevices), perfectly matching edge borders designed for continuous "
                             "repeating pattern tiling in a 3D game engine."),
            "negative_prompt": "perspective angle, strong directional shadows, light falloff, vignette, isolated objects in center, non-repeating edges, blur",
            "aspect_ratio": "1:1",
            "width": 1024,
            "height": 1024,
            "steps": 50,
            "guidance": 4.5,
            "game_asset_meta": {
                "asset_type": "tileable_texture",
                "isolated_background": False
            },
            "suggested_directory": "game_assets",
            "quality_checklist": [
                "Vue perpendiculaire plane sans angle",
                "Éclairage neutre et homogène sans ombres portées",
                "Bords continus pour raccord parfait"
            ]
        }

    elif cat == "stylized_pixar_3d":
        return {
            "category": "stylized_pixar_3d",
            "title": f"Style Pixar 3D - {subj[:32]}",
            "human_prompt": (f"A charming high-end 3D animated film render of {subj} in modern Pixar / Disney feature animation style. "
                             "Expressive character appeal with warm subsurface scattering skin, beautifully sculpted volumetric hair, "
                             "big emotive eyes with glossy catchlights, rich tactile clothing fabric textures, illuminated by warm cinematic "
                             "key lighting and soft complementary rim-light against a gently out-of-focus background."),
            "negative_prompt": "flat 2d, sketch, realistic photograph, horror, uncanny valley, harsh shadows, low poly, blurry, watermark",
            "aspect_ratio": "2:3",
            "width": 832,
            "height": 1216,
            "steps": 50,
            "guidance": 4.2,
            "suggested_directory": "stylized",
            "quality_checklist": [
                "Subsurface scattering chaleureux et doux",
                "Yeux expressifs et brillants",
                "Volumes de cheveux sculptés organiques",
                "Ambiance de long-métrage d'animation haut de gamme"
            ]
        }

    elif cat == "stylized_anime_ghibli":
        named_style = bool(re.search(r"\b(ghibli|shinkai|makoto)\b", raw_input, re.I))
        return {
            "category": "stylized_anime_ghibli",
            "title": f"Style Anime - {subj[:32]}",
            "human_prompt": (f"An anime illustration of {subj}. Delicate precise linework, crisp cel-shaded colors, "
                             "clean contours and carefully drawn anatomy. "
                             + ("Hand-painted environment details in the requested animation style. " if named_style else "")
                             + "Preserve the requested subject, setting, colors and composition."),
            "negative_prompt": "photorealistic, realistic skin pores, 3d CGI render, western cartoon, dark gritty, muddy textures, watermark",
            "aspect_ratio": "3:2",
            "width": 1216,
            "height": 832,
            "steps": 50,
            "guidance": 4.2,
            "suggested_directory": "stylized",
            "quality_checklist": [
                "Lignes épurées et cel-shading soigné",
                "Sujet, décor et cadrage conformes à la demande",
                "Style demandé sans ajout d'un autre artiste"
            ]
        }

    elif cat == "stylized_manga_ink":
        return {
            "category": "stylized_manga_ink",
            "title": f"Manga Encre N&B - {subj[:32]}",
            "human_prompt": (f"A dynamic black and white manga splash illustration featuring {subj}. Masterful traditional ink line "
                             "hierarchy with bold contours and fine hatching, authentic screentone dot patterns for midtones, deep black "
                             "ink fills, dynamic composition with expressive speedlines, strictly monochrome with crisp contrast."),
            "negative_prompt": "color, pastel, watercolor, 3d render, realistic photo, blurry gray wash, anti-aliased gradient, watermark",
            "aspect_ratio": "2:3",
            "width": 832,
            "height": 1216,
            "steps": 50,
            "guidance": 4.8,
            "suggested_directory": "stylized",
            "quality_checklist": [
                "Noir et blanc strict avec trames lisibles",
                "Encrage dynamique avec hiérarchie des traits",
                "Contraste d'impression manga professionnel"
            ]
        }

    elif cat == "stylized_cyberpunk":
        return {
            "category": "stylized_cyberpunk",
            "title": f"Cyberpunk Neon - {subj[:32]}",
            "human_prompt": (f"A cinematic cyberpunk visual scene capturing {subj}. Drenched in vivid neon lights (electric cyan, magenta, "
                             "and deep amber) reflecting off rain-slicked asphalt, dense architectural layers with holographic advertisements, "
                             "atmospheric steam and volumetric haze, moody noir contrast with rich dark shadows."),
            "negative_prompt": "daylight, cartoon, pastel, flat illustration, low contrast, washed out colors, blurry, watermark",
            "aspect_ratio": "3:2",
            "width": 1216,
            "height": 832,
            "steps": 50,
            "guidance": 4.2,
            "suggested_directory": "stylized",
            "quality_checklist": [
                "Reflets néon dynamiques sur surfaces mouillées/métalliques",
                "Atmosphère volumique et brume",
                "Profondeur urbaine dense et lisible"
            ]
        }

    elif cat == "stylized_oil_painting":
        return {
            "category": "stylized_oil_painting",
            "title": f"Peinture à l'Huile - {subj[:32]}",
            "human_prompt": (f"A masterful classical oil painting on linen canvas depicting {subj}. Rich textured impasto brushwork "
                             "following the contours of the form, dramatic chiaroscuro illumination reminiscent of Caravaggio and Rembrandt, "
                             "deep glazed transparent shadows, and authentic craquelure and canvas grain texture."),
            "negative_prompt": "digital art, smooth airbrush, vector flat, photograph, 3d render, plastic look, watermark",
            "aspect_ratio": "4:3",
            "width": 1152,
            "height": 896,
            "steps": 50,
            "guidance": 4.0,
            "suggested_directory": "stylized",
            "quality_checklist": [
                "Matière de peinture à l'huile et coups de pinceau visibles",
                "Chiaroscuro profond et contrastes classiques",
                "Texture de toile et patine authentique"
            ]
        }

    elif cat == "stylized_watercolor":
        return {
            "category": "stylized_watercolor",
            "title": f"Aquarelle Fine - {subj[:32]}",
            "human_prompt": (f"An exquisite traditional watercolor painting on cold-press textured cotton paper depicting {subj}. "
                             "Delicate transparent pigment washes, soft wet-on-wet color blooms, natural granulation along the water "
                             "edges, white paper reserves for specular highlights, and graceful calligraphic brush accents."),
            "negative_prompt": "digital flat, hard vector outlines, oil impasto, 3d render, plastic gradient, photograph, watermark",
            "aspect_ratio": "3:2",
            "width": 1216,
            "height": 832,
            "steps": 50,
            "guidance": 3.8,
            "suggested_directory": "stylized",
            "quality_checklist": [
                "Transparence des lavis et fusions d'eau naturelles",
                "Grain du papier aquarelle visible",
                "Réserves de blanc du papier pour la lumière"
            ]
        }

    elif cat == "concept_art_production":
        return {
            "category": "concept_art_production",
            "title": f"Concept Art Épique - {subj[:32]}",
            "human_prompt": (f"An epic production concept art matte painting of {subj}. Cinematic widescreen composition with "
                             "breathtaking scale, dramatic golden atmospheric lighting cutting through fog and clouds, clear "
                             "foreground-to-background spatial depth layering, and production-ready architectural and environmental design."),
            "negative_prompt": "amateur sketch, blurry, flat lighting, messy composition, low resolution, watermark, signature",
            "aspect_ratio": "16:9",
            "width": 1344,
            "height": 768,
            "steps": 50,
            "guidance": 4.0,
            "suggested_directory": "stylized",
            "quality_checklist": [
                "Composition cinématographique avec grande échelle",
                "Éclairage et atmosphère dramatiques",
                "Profondeur de plan lisible (avant/moyen/arrière plan)"
            ]
        }

    raise ValueError(f"Unsupported image category: {cat}")


# Keep the existing category identifiers used by manifests and clients.
_FOREGROUND_STYLES = {
    "photo_realistic": "A detailed photograph with natural materials and accurate colors",
    "game_asset_pixel_art": "A crisp pixel art sprite with readable pixel clusters",
    "game_asset_isometric": "A clean orthographic isometric illustration",
    "game_asset_icon_ui": "A crisp inventory icon with a clearly readable silhouette",
    "game_asset_texture": "An evenly lit orthographic texture",
    "game_asset_3d_prop": "A detailed game prop render with readable geometry",
    "stylized_pixar_3d": "A polished stylized 3D animation render",
    "stylized_anime_ghibli": "An anime illustration with precise linework and crisp cel-shaded colors",
    "stylized_manga_ink": "A monochrome manga illustration with clean ink contours and screentones",
    "stylized_cyberpunk": "A cyberpunk illustration with neon accents on the subject",
    "stylized_oil_painting": "An oil painting with visible brushwork and textured pigments",
    "stylized_watercolor": "A watercolor illustration with delicate transparent washes",
    "concept_art_production": "A detailed production concept illustration",
}


def _uniform_background(raw_input: str) -> Optional[str]:
    """Recognise explicit solid colors; do not infer transparency or a setting."""
    text = strip_accents(raw_input.lower())
    colors = {
        "white": "white|blanc|blanche", "black": "black|noir|noire",
        "gray": "gray|grey|gris|grise", "blue": "blue|bleu|bleue",
        "green": "green|vert|verte", "red": "red|rouge",
    }
    for color, words in colors.items():
        pattern = (rf"\b(?:(?:(?:plain|solid|uniform|clean)\s+)*(?:{words})\s+background"
                   rf"|fond\s+(?:(?:uni|uniforme)\s+)?(?:{words})(?:\s+uni)?)\b")
        for match in re.finditer(pattern, text):
            prefix = text[max(0, match.start() - 32):match.start()]
            if re.search(r"\b(?:sans|pas de|no|not|avoid|without)\s+(?:(?:a|any|un|de)\s+)?$", prefix):
                continue
            return color
    return None


def direct_prompt(raw_input: str, force_category: Optional[str] = None) -> Dict[str, Any]:
    cat = force_category or detect_category(raw_input)
    if cat not in _FOREGROUND_STYLES:
        raise ValueError(f"Unsupported image category: {cat}")
    # The former prop category had no template and silently lost the user's brief.
    spec = _style_prompt(raw_input, cat)
    spec["category"] = cat
    background = _uniform_background(raw_input)
    if background:
        spec["human_prompt"] = (
            f"{_FOREGROUND_STYLES[cat]}. Subject and requested details: {raw_input.strip()}. "
            f"Use a plain solid {background} background throughout the frame. "
            "Follow the requested framing and viewpoint. Preserve all requested features, objects, colors and pose."
        )
        spec["quality_checklist"] = [
            f"Fond {background} uni conforme à la demande",
            "Sujet, objets, couleurs et pose conformes au texte original",
            "Cadrage et visibilité conformes à la demande",
        ]
        spec["requested_background"] = background
    text = strip_accents(raw_input.lower())
    full_body = bool(re.search(r"\b(full[- ]body|head[- ]to[- ]toe|en pied|corps entier)\b", text))
    explicit_ratio = re.search(r"\b(1\s*:\s*1|2\s*:\s*3|3\s*:\s*2|16\s*:\s*9|9\s*:\s*16)\b", text)
    dimensions = {"1:1": (1024, 1024), "2:3": (832, 1216), "3:2": (1216, 832),
                  "16:9": (1344, 768), "9:16": (768, 1344)}
    ratio = re.sub(r"\s", "", explicit_ratio.group()) if explicit_ratio else None
    upright_character = bool(re.search(r"\b(character|personnage|personne|woman|man|femme|homme|girl|boy)\b", text))
    if ratio is None and full_body and upright_character and not re.search(r"\b(landscape|horizontal|panorami\w*|wide[- ]screen)\b", text):
        ratio = "2:3"
    if ratio:
        spec["width"], spec["height"] = dimensions[ratio]
        spec["aspect_ratio"] = ratio
    return spec
