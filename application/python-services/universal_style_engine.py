#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""universal_style_engine.py — Moteur universel de synthèse et taxonomie multi-styles 2D & 3D.

Combine :
1. Les 8 archétypes fondamentaux calibrés (`STYLE_PROFILES`) pour une compatibilité
   instantanée et déterministe.
2. Un synthétiseur continu par premiers principes physiques et géométriques
   (`synthesize_dynamic_style_profile`) capable d'analyser et de comprendre
   N'IMPORTE QUEL style inédit, hybride ou descriptif sans aucun précodage figé
   (ex: porcelaine Kintsugi à veines d'or, vitrail gothique plombé, gravure sur
   bois Ukiyo-e, chitine biomécanique irisée, steampunk laiton brossé, origami
   kirigami papier washi, laine tricotée amigurumi, bronze patiné, synthwave
   holographique, aquarelle sumi-e, marbre sculpté, etc.).

Décompose toute requête sur 7 axes continus :
- Axe 1 : Topologie & acuité d'arêtes (`AURORA_TRELLIS2_REMESH`, `AURORA_TRELLIS2_REMESH_PROJECT`, `AURORA_GALBE_2D`)
- Axe 2 : Micro-relief tangentiel & anisotropie (`normal_strength`, `anisotropyStrength`, `anisotropyRotation`)
- Axe 3 : Cartographie matérielle multi-zones par texel (`multi_zone_cartography`, `vein_metallic_boost`, `outline_matte_lock`)
- Axe 4 : Réfraction, spécularité & vernis (`ior`, `specularFactor`, `clearcoatFactor`, `clearcoatRoughnessFactor`)
- Axe 5 : Transmission volumétrique & absorption (`transmissionFactor`, `attenuationDistance`, `attenuationColor`)
- Axe 6 : Iridescence couche mince & sheen microfibres (`iridescenceFactor`, `iridescenceIor`, `sheenColorFactor`, `sheenRoughnessFactor`)
- Axe 7 : Garde-fous 2D dynamiques sur-mesure (`2d_positive_guardrails`, `2d_negative_guardrails`)
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "cartoon_2d_flat": {
        "label": "Cartoon 2D Franco-Belge / Xilam / Animation 2D",
        "triggers": (
            r"\b(zig\s*et\s*sharko|zig\s+and\s+sharko|xilam|oggy|dalton|lucky\s+luke|"
            r"tex\s+avery|looney\s+tunes|cartoon\s+2d|dessin\s+anim[eé]\s+2d|flat\s+2d|"
            r"franco[- ]belge|bob\s+l'eponge|spongebob|simpsons|tom\s+et\s+jerry)\b"
        ),
        "2d_positive_guardrails": (
            "official 2D cartoon character model sheet, full body standing upright facing forward, "
            "clean thick closed black ink outlines completely enclosing the eyes and white sclera, "
            "closed or cheerful smiling mouth without dark chest cavity, vibrant flat cel colors, "
            "well-separated characters on pure solid white studio background, no pedestal, no base"
        ),
        "2d_negative_guardrails": (
            "open unclosed eye rims, white sclera merging into white background, giant black gaping mouth, "
            "photorealistic skin, 3d pedestal, round stand, cropped feet, blurry gradients"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "1",
            "AURORA_MULTI_CHARACTER_3D": "1",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.5",
            "AURORA_ROUGHNESS_FLOOR": "0.68",
        },
        "pbr_profile": {
            "roughness_floor": 0.68,
            "roughness_ceil": 0.94,
            "normal_strength": 0.009,
            "cavity_ao_min": 120.0,
            "ior": 1.44,
            "specularFactor": 0.35,
            "clearcoatFactor": 0.0,
            "metallic_scale": 0.40,
            "occlusionStrength": 0.55,
            "multi_zone_cartography": True,
            "outline_matte_lock": True,
        },
    },
    "anime_cel": {
        "label": "Anime Japonais / Cel-Shading (Level-5, Ghibli, Shonen)",
        "triggers": (
            r"\b(inazuma\s+eleven|mark\s+evans|endou\s+mamoru|jibanyan|yo[- ]?kai\s+watch|"
            r"anime|manga\s+color|cel[- ]shad|ghibli|naruto|dragon\s+ball|one\s+piece|pokemon)\b"
        ),
        "2d_positive_guardrails": (
            "official anime character key visual, full body standing front view, crisp closed lineart, "
            "smooth unified skin tone without harsh dark cheek shadow blotches, pure white highlights "
            "preserved on eyes and accessories, pure white studio background, no stand"
        ),
        "2d_negative_guardrails": (
            "harsh brown facial shadow scar, dirty grey shading on white ball or sclera, "
            "plastic pedestal, fused arms, extra limbs"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "1",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.5",
            "AURORA_ROUGHNESS_FLOOR": "0.64",
        },
        "pbr_profile": {
            "roughness_floor": 0.64,
            "roughness_ceil": 0.92,
            "normal_strength": 0.010,
            "cavity_ao_min": 115.0,
            "ior": 1.45,
            "specularFactor": 0.42,
            "clearcoatFactor": 0.0,
            "metallic_scale": 0.55,
            "occlusionStrength": 0.60,
            "multi_zone_cartography": True,
            "outline_matte_lock": True,
        },
    },
    "figurine_collector": {
        "label": "Figurine Collector 3D / Vinyle / Resine Studio",
        "triggers": (
            r"\b(figurine|statuette|nendoroid|funko|amiibo|vinyle|vinyl\s+toy|collector\s+figure|"
            r"jouet\s+3d|action\s+figure)\b"
        ),
        "2d_positive_guardrails": (
            "high-end 3D collector vinyl figurine, smooth tactile satin PVC and resin materials, "
            "soft studio global illumination, full body standing directly on flat ground without any base "
            "or pedestal, clean silhouette separation on solid white studio background"
        ),
        "2d_negative_guardrails": (
            "circular pedestal, black base, plinth, display stand, wet latex glare, flat 2d paper cutout"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "0",
            "AURORA_MULTI_CHARACTER_3D": "1",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.5",
            "AURORA_ROUGHNESS_FLOOR": "0.42",
        },
        "pbr_profile": {
            "roughness_floor": 0.38,
            "roughness_ceil": 0.80,
            "normal_strength": 0.015,
            "cavity_ao_min": 88.0,
            "ior": 1.49,
            "specularFactor": 0.78,
            "clearcoatFactor": 0.22,
            "clearcoatRoughnessFactor": 0.14,
            "metallic_scale": 1.0,
            "occlusionStrength": 0.75,
            "multi_zone_cartography": True,
        },
    },
    "voxel_cubic": {
        "label": "Style Cubique / Voxel / Minecraft / Low-Poly Orthogonal",
        "triggers": (
            r"\b(cubique|voxel|minecraft|blocky|lego|roblox|low[- ]?poly\s+cube|8[- ]?bit\s+3d)\b"
        ),
        "2d_positive_guardrails": (
            "authentic 3D cubic voxel character, crisp 90-degree orthogonal block geometry, "
            "clean pixel-art block textures without organic rounding, standing full body on white background, "
            "no pedestal"
        ),
        "2d_negative_guardrails": (
            "smooth organic curves, melted corners, spherical head, round base, blurry textures"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "0",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.88",
            "AURORA_ROUGHNESS_FLOOR": "0.66",
        },
        "pbr_profile": {
            "roughness_floor": 0.66,
            "roughness_ceil": 0.94,
            "normal_strength": 0.008,
            "cavity_ao_min": 100.0,
            "ior": 1.45,
            "specularFactor": 0.40,
            "clearcoatFactor": 0.0,
            "metallic_scale": 0.80,
            "occlusionStrength": 0.70,
            "multi_zone_cartography": True,
        },
    },
    "comic_manga_ink": {
        "label": "Bande Dessinee / Comics / Ligne Claire / Manga Encre",
        "triggers": (
            r"\b(bande\s+dessin[eé]e|ligne\s+claire|tintin|ast[eé]rix|comics|marvel\s+comic|"
            r"encrage\s+bd|halftone|trame\s+manga)\b"
        ),
        "2d_positive_guardrails": (
            "classic Franco-Belgian ligne claire comic illustration, uniform closed black ink outlines, "
            "clean luminous flat colors without heavy crosshatching on the face, full body on white background"
        ),
        "2d_negative_guardrails": (
            "broken outlines, heavy black facial blotches, photorealistic render, 3d base"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "1",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.5",
            "AURORA_ROUGHNESS_FLOOR": "0.66",
        },
        "pbr_profile": {
            "roughness_floor": 0.65,
            "roughness_ceil": 0.94,
            "normal_strength": 0.011,
            "cavity_ao_min": 110.0,
            "ior": 1.45,
            "specularFactor": 0.38,
            "clearcoatFactor": 0.0,
            "metallic_scale": 0.50,
            "occlusionStrength": 0.60,
            "multi_zone_cartography": True,
            "outline_matte_lock": True,
        },
    },
    "clay_stopmotion": {
        "label": "Pate a Modeler / Claymation / Stop-Motion",
        "triggers": (
            r"\b(claymation|p[aâ]te\s+[aà]\s+modeler|stop[- ]?motion|aardman|plasticine)\b"
        ),
        "2d_positive_guardrails": (
            "handcrafted stop-motion claymation sculpture, matte plasticine surface with subtle tactile "
            "craftsmanship, soft studio lighting on pure white background, no stand"
        ),
        "2d_negative_guardrails": (
            "glossy chrome, wet plastic, flat 2d vector, pedestal"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "0",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.5",
            "AURORA_ROUGHNESS_FLOOR": "0.78",
        },
        "pbr_profile": {
            "roughness_floor": 0.76,
            "roughness_ceil": 0.97,
            "normal_strength": 0.022,
            "cavity_ao_min": 82.0,
            "ior": 1.43,
            "specularFactor": 0.22,
            "clearcoatFactor": 0.0,
            "metallic_scale": 0.15,
            "sheenColorFactor": [0.06, 0.06, 0.06],
            "sheenRoughnessFactor": 0.85,
            "occlusionStrength": 0.80,
            "multi_zone_cartography": True,
        },
    },
    "crystal_glossy": {
        "label": "Cristal / Verre / Metal Poli / Matiere Speculaire",
        "triggers": (
            r"\b(cristal|verre|glass|crystal|diamant|diamond|chrome|or\s+poli|glossy|translucide|transparent|refractif|refractive)\b"
        ),
        "2d_positive_guardrails": (
            "optically clear faceted crystal and refractive glass material, crisp caustics and specular "
            "highlights, clean outer silhouette on neutral studio background, isolated physical object only"
        ),
        "2d_negative_guardrails": (
            "matte chalk, opaque mud, flat unlit color, opaque plastic balloon, person, human, hands"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "0",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.68",
            "AURORA_ROUGHNESS_FLOOR": "0.04",
        },
        "pbr_profile": {
            "is_optical_crystal_glass": True,
            "roughness_floor": 0.04,
            "roughness_ceil": 0.35,
            "normal_strength": 0.016,
            "cavity_ao_min": 120.0,
            "ior": 1.62,
            "specularFactor": 1.0,
            "clearcoatFactor": 0.92,
            "clearcoatRoughnessFactor": 0.03,
            "transmissionFactor": 0.88,
            "attenuationDistance": 0.35,
            "thicknessFactor": 0.24,
            "alphaMode": "BLEND",
            "baseColorAlpha": 0.68,
            "metallic_scale": 0.0,
            "occlusionStrength": 0.55,
            "multi_zone_cartography": True,
        },
    },
    "realistic_pbr": {
        "label": "Photorealisme PBR / Cinema / Haute Fidelite",
        "triggers": r".*",
        "2d_positive_guardrails": (
            "physically based studio photography, natural balanced key and fill lighting without harsh "
            "cast shadows, sharp anatomical and material fidelity on clean studio background"
        ),
        "2d_negative_guardrails": (
            "overexposed specular plastic skin, harsh black shadows, deformed anatomy, pedestal"
        ),
        "3d_env": {
            "AURORA_GALBE_2D": "0",
            "AURORA_TRELLIS2_REMESH": "1",
            "AURORA_TRELLIS2_REMESH_PROJECT": "0.5",
            "AURORA_ROUGHNESS_FLOOR": "0.14",
        },
        "pbr_profile": {
            "roughness_floor": 0.14,
            "roughness_ceil": 0.95,
            "normal_strength": 0.018,
            "cavity_ao_min": 80.0,
            "ior": 1.48,
            "specularFactor": 0.68,
            "clearcoatFactor": 0.0,
            "metallic_scale": 1.0,
            "occlusionStrength": 0.75,
            "multi_zone_cartography": True,
        },
    },
}

_PRIORITY_ORDER = (
    "figurine_collector",
    "voxel_cubic",
    "crystal_glossy",
    "clay_stopmotion",
    "cartoon_2d_flat",
    "anime_cel",
    "comic_manga_ink",
    "realistic_pbr",
)


# Descripteurs physiques et artistiques continus pour comprendre TOUT style nouveau ou hybride
_DYNAMIC_MATERIAL_DESCRIPTORS: list[dict[str, Any]] = [
    {
        "tag": "kintsugi_porcelain",
        "label": "Porcelaine Kintsugi & Céramique Émaillée à Veines d'Or",
        "pattern": r"\b(kintsugi|porcelaine|porcelain|c[eé]ramique|ceramic|fa[iï]ence|raku|[eé]mail|glazed\s+pottery)\b",
        "positive_2d": (
            "fine handcrafted glazed porcelain sculpture with authentic gold lacquer kintsugi veins, "
            "crisp specular ceramic glaze, pure studio white background, no stand"
        ),
        "negative_2d": "matte plastic, blurry mud, flat paper, pedestal",
        "remesh_project": 0.56,
        "pbr_delta": {
            "roughness_floor": 0.08,
            "roughness_ceil": 0.48,
            "normal_strength": 0.021,
            "cavity_ao_min": 95.0,
            "ior": 1.56,
            "specularFactor": 0.92,
            "clearcoatFactor": 0.78,
            "clearcoatRoughnessFactor": 0.03,
            "metallic_scale": 1.25,
            "multi_zone_cartography": True,
            "vein_metallic_boost": True,
        },
    },
    {
        "tag": "stained_glass_gothic",
        "label": "Vitrail Gothique Plombé & Verre Cathédrale Translucide",
        "pattern": r"\b(vitrail|stained\s+glass|verre\s+cath[eé]drale|plomb[eé]|lead\s+caming|mosaic\s+glass|tiffanys?\s+lamp)\b",
        "positive_2d": (
            "authentic gothic stained glass artwork with dark lead caming lines and luminous translucent "
            "colored glass segments, crisp geometric facets on clean white background"
        ),
        "negative_2d": "opaque chalk, blurry unsegmented gradients, pedestal",
        "remesh_project": 0.74,
        "pbr_delta": {
            "roughness_floor": 0.05,
            "roughness_ceil": 0.75,
            "normal_strength": 0.024,
            "cavity_ao_min": 90.0,
            "ior": 1.62,
            "specularFactor": 0.95,
            "clearcoatFactor": 0.60,
            "clearcoatRoughnessFactor": 0.02,
            "transmissionFactor": 0.64,
            "attenuationDistance": 0.35,
            "attenuationColor": [0.92, 0.85, 0.68],
            "metallic_scale": 0.90,
            "multi_zone_cartography": True,
            "outline_matte_lock": True,
        },
    },
    {
        "tag": "ukiyoe_woodblock",
        "label": "Gravure sur Bois Ukiyo-e / Sculpture Bois / Bas-Relief",
        "pattern": r"\b(ukiyo[- ]?e|woodblock|gravure\s+sur\s+bois|bois\s+sculpt[eé]|carved\s+wood|ebene|acajou|bambou|menuiserie|linogravure|estampe)\b",
        "positive_2d": (
            "masterpiece carved woodblock sculpture with visible fine wood grain relief and sumi ink contours, "
            "natural warm timber pigments on pure white background, no stand"
        ),
        "negative_2d": "glossy wet chrome, neon plastic, pedestal",
        "remesh_project": 0.62,
        "pbr_delta": {
            "roughness_floor": 0.52,
            "roughness_ceil": 0.92,
            "normal_strength": 0.026,
            "cavity_ao_min": 78.0,
            "ior": 1.47,
            "specularFactor": 0.38,
            "clearcoatFactor": 0.12,
            "clearcoatRoughnessFactor": 0.28,
            "anisotropyStrength": 0.48,
            "anisotropyRotation": 0.0,
            "metallic_scale": 0.25,
            "multi_zone_cartography": True,
            "outline_matte_lock": True,
        },
    },
    {
        "tag": "iridescent_biomech_chitin",
        "label": "Chitine Biomécanique Irisée / Nacre / Couche Mince Optique",
        "pattern": r"\b(chitine|chitin|iris[eé]|iridescen|scarab[eé]e|nacre|mother\s+of\s+pearl|opale|opal|holograph|dichro[iï]c|biom[eé]canique|biomechanical|anodis[eé])\b",
        "positive_2d": (
            "intricate iridescent biomechanical chitin carapace with structural thin-film color shift, "
            "razor-sharp articulated plates on clean white studio background, no pedestal"
        ),
        "negative_2d": "flat matte chalk, blurry silhouette, pedestal",
        "remesh_project": 0.64,
        "pbr_delta": {
            "roughness_floor": 0.10,
            "roughness_ceil": 0.58,
            "normal_strength": 0.022,
            "cavity_ao_min": 76.0,
            "ior": 1.58,
            "specularFactor": 0.94,
            "clearcoatFactor": 0.52,
            "clearcoatRoughnessFactor": 0.06,
            "iridescenceFactor": 0.85,
            "iridescenceIor": 1.38,
            "iridescenceThicknessMinimum": 140.0,
            "iridescenceThicknessMaximum": 420.0,
            "metallic_scale": 0.85,
            "multi_zone_cartography": True,
        },
    },
    {
        "tag": "steampunk_brushed_metal",
        "label": "Steampunk / Laiton Brossé / Cuivre Patiné / Horlogerie Mécanique",
        "pattern": r"\b(steampunk|clockwork|horlogerie|laiton|brass|cuivre|copper|bronze|patin[eé]|verdigris|vert[- ]de[- ]gris|acier\s+bross[eé]|brushed\s+metal|engrenage|m[eé]canique)\b",
        "positive_2d": (
            "precision engineered steampunk mechanical assembly in brushed brass, copper and patinated bronze, "
            "crisp chamfers, gears and rivets on pure white studio background, no stand"
        ),
        "negative_2d": "melted organic blobs, blurry edges, flat cartoon, pedestal",
        "remesh_project": 0.72,
        "pbr_delta": {
            "roughness_floor": 0.16,
            "roughness_ceil": 0.78,
            "normal_strength": 0.024,
            "cavity_ao_min": 72.0,
            "ior": 1.52,
            "specularFactor": 0.95,
            "anisotropyStrength": 0.68,
            "anisotropyRotation": 0.52,
            "metallic_scale": 1.35,
            "multi_zone_cartography": True,
            "vein_metallic_boost": True,
        },
    },
    {
        "tag": "origami_kirigami_washi",
        "label": "Origami / Kirigami / Papier Plié Washi / Papercraft",
        "pattern": r"\b(origami|kirigami|papercraft|papier\s+pli[eé]|washi|folded\s+paper|carton\s+découp[eé]|low[- ]?poly\s+paper)\b",
        "positive_2d": (
            "authentic geometric origami and kirigami folded washi paper sculpture, razor-sharp planar "
            "creases and layered paper fibers, standing on pure white background, no pedestal"
        ),
        "negative_2d": "wet glossy plastic, rounded melted spheres, chrome, pedestal",
        "remesh_project": 0.82,
        "pbr_delta": {
            "roughness_floor": 0.74,
            "roughness_ceil": 0.96,
            "normal_strength": 0.019,
            "cavity_ao_min": 84.0,
            "ior": 1.42,
            "specularFactor": 0.24,
            "clearcoatFactor": 0.0,
            "sheenColorFactor": [0.09, 0.09, 0.08],
            "sheenRoughnessFactor": 0.82,
            "metallic_scale": 0.10,
            "multi_zone_cartography": True,
        },
    },
    {
        "tag": "textile_amigurumi_knit",
        "label": "Amigurumi / Crochet / Laine Tricotée / Feutrine / Peluche",
        "pattern": r"\b(amigurumi|crochet|tricot|knitted|laine|wool|feutrine|felt|peluche|plush|tissu|broderie|embroidery|velours|velvet)\b",
        "positive_2d": (
            "handcrafted knitted wool amigurumi crochet character with crisp visible yarn stitches and "
            "soft microfiber sheen, standing full body on pure white studio background, no stand"
        ),
        "negative_2d": "glossy metal, wet plastic skin, hard chrome, pedestal",
        "remesh_project": 0.52,
        "pbr_delta": {
            "roughness_floor": 0.80,
            "roughness_ceil": 0.98,
            "normal_strength": 0.028,
            "cavity_ao_min": 74.0,
            "ior": 1.41,
            "specularFactor": 0.18,
            "clearcoatFactor": 0.0,
            "sheenColorFactor": [0.16, 0.16, 0.16],
            "sheenRoughnessFactor": 0.78,
            "metallic_scale": 0.05,
            "multi_zone_cartography": True,
        },
    },
    {
        "tag": "cyber_synthwave_neon",
        "label": "Cyberpunk / Synthwave / Néon Holographique / Tron",
        "pattern": r"\b(synthwave|cyberpunk|outrun|vaporwave|tron|n[eé]on\s+grid|cyber[- ]?samurai|futuriste\s+lumineux)\b",
        "positive_2d": (
            "high-contrast cyberpunk synthwave design with crisp glowing neon circuitry seams and sleek "
            "satin carbon-polymer armor plates on clean white background, no pedestal"
        ),
        "negative_2d": "muddy desaturated brown, blurry edges, pedestal",
        "remesh_project": 0.66,
        "pbr_delta": {
            "roughness_floor": 0.12,
            "roughness_ceil": 0.72,
            "normal_strength": 0.020,
            "cavity_ao_min": 75.0,
            "ior": 1.54,
            "specularFactor": 0.88,
            "clearcoatFactor": 0.38,
            "clearcoatRoughnessFactor": 0.05,
            "emissiveStrength": 2.8,
            "iridescenceFactor": 0.45,
            "iridescenceIor": 1.35,
            "metallic_scale": 1.15,
            "multi_zone_cartography": True,
            "vein_metallic_boost": True,
        },
    },
    {
        "tag": "marble_stone_sculpture",
        "label": "Marbre de Carrare / Pierre Sculptée / Albâtre / Jade",
        "pattern": r"\b(marbre|marble|alb[aâ]tre|alabaster|jade|granit|pierre\s+sculpt[eé]e|statue\s+antique|obsidienne|terracotta|terre\s+cuite)\b",
        "positive_2d": (
            "museum-grade carved Carrara marble and stone sculpture with crisp chisel definition and subtle "
            "mineral veining on pure white studio background, no plinth"
        ),
        "negative_2d": "plastic toy, flat 2d cartoon, neon glare",
        "remesh_project": 0.58,
        "pbr_delta": {
            "roughness_floor": 0.22,
            "roughness_ceil": 0.76,
            "normal_strength": 0.021,
            "cavity_ao_min": 80.0,
            "ior": 1.55,
            "specularFactor": 0.72,
            "clearcoatFactor": 0.18,
            "clearcoatRoughnessFactor": 0.12,
            "transmissionFactor": 0.14,
            "attenuationDistance": 0.80,
            "attenuationColor": [0.96, 0.94, 0.90],
            "metallic_scale": 0.20,
            "multi_zone_cartography": True,
        },
    },
    {
        "tag": "watercolor_sumie_painterly",
        "label": "Aquarelle / Sumi-e / Gouache / Peinture Impressionniste",
        "pattern": r"\b(aquarelle|watercolor|sumi[- ]?e|gouache|peinture\s+[aà]\s+l'huile|oil\s+painting|impasto|pastel|fusain|charcoal)\b",
        "positive_2d": (
            "expressive fine-art painterly illustration with crisp calligraphed sumi-e ink accents and "
            "luminous pigment washes, full subject isolated on pure white paper background, no stand"
        ),
        "negative_2d": "glossy plastic 3d render, chrome glare, pedestal",
        "remesh_project": 0.52,
        "pbr_delta": {
            "roughness_floor": 0.72,
            "roughness_ceil": 0.96,
            "normal_strength": 0.017,
            "cavity_ao_min": 96.0,
            "ior": 1.43,
            "specularFactor": 0.28,
            "clearcoatFactor": 0.0,
            "sheenColorFactor": [0.07, 0.07, 0.07],
            "sheenRoughnessFactor": 0.86,
            "metallic_scale": 0.20,
            "multi_zone_cartography": True,
            "outline_matte_lock": True,
        },
    },
    {
        "tag": "volcanic_black_opal",
        "label": "Opale Noire Volcanique à Feu Spectral & Silice Irisée",
        "pattern": r"\b(opale\s+noire|black\s+opal|feu\s+spectral|spectral\s+fire|opale\s+volcanique|volcanic\s+opal)\b",
        "positive_2d": (
            "precious volcanic black opal sculpture with deep obsidian matrix and vibrant internal spectral "
            "fire diffraction flashes in emerald, cyan and crimson, crisp studio silhouette on white background"
        ),
        "negative_2d": "flat matte grey, dull plastic, pedestal",
        "remesh_project": 0.62,
        "pbr_delta": {
            "roughness_floor": 0.06,
            "roughness_ceil": 0.42,
            "normal_strength": 0.019,
            "cavity_ao_min": 84.0,
            "ior": 1.46,
            "specularFactor": 0.96,
            "clearcoatFactor": 0.72,
            "clearcoatRoughnessFactor": 0.03,
            "transmissionFactor": 0.24,
            "attenuationDistance": 0.30,
            "attenuationColor": [0.12, 0.38, 0.52],
            "iridescenceFactor": 0.96,
            "iridescenceIor": 1.42,
            "iridescenceThicknessMinimum": 180.0,
            "iridescenceThicknessMaximum": 520.0,
            "emissiveStrength": 1.6,
            "metallic_scale": 0.65,
            "multi_zone_cartography": True,
        },
    },
    {
        "tag": "dichromatic_spatial_glass",
        "label": "Verre Dichromatique Spatial & Optique Interférentielle",
        "pattern": r"\b(verre\s+dichromatique|dichroic\s+glass|dichromatique|spatial\s+glass|prisme\s+dichro[iï]que)\b",
        "positive_2d": (
            "aerospace dichroic optical glass sculpture with thin-film interference coatings shifting between "
            "cobalt cyan, magenta and gold, razor-sharp refractive facets on pure white background"
        ),
        "negative_2d": "opaque mud, chalky surface, pedestal",
        "remesh_project": 0.72,
        "pbr_delta": {
            "roughness_floor": 0.04,
            "roughness_ceil": 0.32,
            "normal_strength": 0.015,
            "cavity_ao_min": 115.0,
            "ior": 1.68,
            "specularFactor": 1.0,
            "clearcoatFactor": 0.80,
            "clearcoatRoughnessFactor": 0.02,
            "transmissionFactor": 0.72,
            "attenuationDistance": 0.40,
            "attenuationColor": [0.35, 0.82, 0.96],
            "iridescenceFactor": 0.92,
            "iridescenceIor": 1.48,
            "iridescenceThicknessMinimum": 160.0,
            "iridescenceThicknessMaximum": 480.0,
            "metallic_scale": 0.95,
            "multi_zone_cartography": True,
        },
    },
    {
        "tag": "anisotropic_damask_silk",
        "label": "Soie Damassée Anisotrope & Brocart Impérial",
        "pattern": r"\b(soie\s+damass[eé]e|damask\s+silk|soie|silk|damass[eé]|damask|brocart|brocade|satin\s+imp[eé]rial|taffetas)\b",
        "positive_2d": (
            "imperial woven damask silk and gold brocade garment with crisp anisotropic thread sheen and "
            "raised floral Jacquard relief, clean studio silhouette on pure white background"
        ),
        "negative_2d": "hard wet plastic, blurry texture, pedestal",
        "remesh_project": 0.56,
        "pbr_delta": {
            "roughness_floor": 0.24,
            "roughness_ceil": 0.68,
            "normal_strength": 0.022,
            "cavity_ao_min": 82.0,
            "ior": 1.54,
            "specularFactor": 0.78,
            "anisotropyStrength": 0.78,
            "anisotropyRotation": 0.38,
            "sheenColorFactor": [0.88, 0.76, 0.48],
            "sheenRoughnessFactor": 0.34,
            "iridescenceFactor": 0.35,
            "iridescenceIor": 1.36,
            "metallic_scale": 1.15,
            "multi_zone_cartography": True,
            "vein_metallic_boost": True,
        },
    },
    {
        "tag": "translucent_amber_jade_wax",
        "label": "Ambre Fossile / Jade Impérial / Cire Translucide / Gelée Bioluminescente",
        "pattern": r"\b(ambre|amber|jade\s+imp[eé]rial|jadeite|n[eé]phrite|cire\s+d'abeille|beeswax|cire\s+translucide|silicone\s+translucide|gel[eé]e\s+abyssale|m[eé]duse|bioluminescen|cornaline|agate|calc[eé]doine|r[eé]sine\s+[eé]poxy)\b",
        "positive_2d": (
            "translucent subsurface-scattering organic mineral material with warm internal volumetric glow "
            "and smooth polished surface on pure white studio background, no pedestal"
        ),
        "negative_2d": "opaque chalk, flat cartoon, harsh black shadows, pedestal",
        "remesh_project": 0.54,
        "pbr_delta": {
            "roughness_floor": 0.08,
            "roughness_ceil": 0.46,
            "normal_strength": 0.016,
            "cavity_ao_min": 92.0,
            "ior": 1.54,
            "specularFactor": 0.88,
            "clearcoatFactor": 0.56,
            "clearcoatRoughnessFactor": 0.04,
            "transmissionFactor": 0.58,
            "attenuationDistance": 0.42,
            "attenuationColor": [0.95, 0.72, 0.28],
            "subsurface_scattering_radius_mm": [2.8, 1.4, 0.6],
            "metallic_scale": 0.15,
            "multi_zone_cartography": True,
        },
    },
    {
        "tag": "volcanic_magma_obsidian",
        "label": "Lave Incandescente / Basalte Vitrifié / Obsidienne & Magma",
        "pattern": r"\b(lave|lava|magma|basalte|basalt|incandescen|braise|ember|volcanique|cro[uû]te\s+de\s+lave|scorie|pierre\s+de\s+lave)\b",
        "positive_2d": (
            "cooled dark volcanic basalt and vitrified obsidian crust fractured by glowing incandescent "
            "magma veins, sharp rock relief on pure white studio background, no stand"
        ),
        "negative_2d": "washed out grey plastic, blurry textures, pedestal",
        "remesh_project": 0.68,
        "pbr_delta": {
            "roughness_floor": 0.14,
            "roughness_ceil": 0.94,
            "normal_strength": 0.028,
            "cavity_ao_min": 70.0,
            "ior": 1.50,
            "specularFactor": 0.76,
            "clearcoatFactor": 0.20,
            "clearcoatRoughnessFactor": 0.08,
            "emissiveStrength": 3.4,
            "metallic_scale": 0.45,
            "multi_zone_cartography": True,
            "vein_metallic_boost": True,
        },
    },
    {
        "tag": "forged_damascus_carbon",
        "label": "Acier de Damas Forgé / Carbone Forgé / Titane Anodisé / Fer Martelé",
        "pattern": r"\b(damas|damascus|carbone\s+forg[eé]|forged\s+carbon|fibre\s+de\s+carbone|carbon\s+fiber|titane|titanium|fer\s+forg[eé]|fer\s+martel[eé]|hammered\s+iron|corten|rouill[eé]\s+patin[eé]|m[eé]t[eé]orite)\b",
        "positive_2d": (
            "precision forged Damascus steel and woven carbon-titanium composite with crisp layered grain "
            "and anisotropic metallic sheen on pure white studio background, no stand"
        ),
        "negative_2d": "flat plastic, blurry mud, pedestal",
        "remesh_project": 0.70,
        "pbr_delta": {
            "roughness_floor": 0.12,
            "roughness_ceil": 0.68,
            "normal_strength": 0.025,
            "cavity_ao_min": 74.0,
            "ior": 1.58,
            "specularFactor": 0.96,
            "clearcoatFactor": 0.34,
            "clearcoatRoughnessFactor": 0.06,
            "anisotropyStrength": 0.74,
            "anisotropyRotation": 0.42,
            "metallic_scale": 1.35,
            "multi_zone_cartography": True,
            "vein_metallic_boost": True,
        },
    },
    {
        "tag": "urushi_celadon_lacquer",
        "label": "Laque Urushi Impériale / Céladon Craquelé / Émail Grand Feu",
        "pattern": r"\b(urushi|laque\s+japonaise|laque\s+chinoise|c[eé]ladon|celadon|craquel[eé]|crackle\s+glaze|[eé]mail\s+grand\s+feu|cloisonn[eé]|champlev[eé])\b",
        "positive_2d": (
            "museum-grade imperial Urushi lacquer and crackle-glazed celadon ceramic with deep mirror "
            "clearcoat over fine crackle network on pure white background, no stand"
        ),
        "negative_2d": "matte chalk, unglazed mud, pedestal",
        "remesh_project": 0.58,
        "pbr_delta": {
            "roughness_floor": 0.05,
            "roughness_ceil": 0.44,
            "normal_strength": 0.018,
            "cavity_ao_min": 88.0,
            "ior": 1.57,
            "specularFactor": 0.95,
            "clearcoatFactor": 0.88,
            "clearcoatRoughnessFactor": 0.02,
            "transmissionFactor": 0.18,
            "attenuationDistance": 0.55,
            "attenuationColor": [0.76, 0.88, 0.80],
            "metallic_scale": 1.10,
            "multi_zone_cartography": True,
            "vein_metallic_boost": True,
        },
    },
    {
        "tag": "glacial_frost_crystal_ice",
        "label": "Glace Arctique / Givre Cristallin / Quartz & Permafrost",
        "pattern": r"\b(glace\s+arctique|glacial|givre|frost|ice\s+crystal|cristal\s+de\s+glace|iceberg|quartz\s+fum[eé]|am[eé]thyste|citrine|topaze|saphir|rubis|[eé]meraude)\b",
        "positive_2d": (
            "optically refractive arctic ice and crystalline frost gemstone with internal caustics and "
            "sharp natural crystal cleavage planes on pure white background, no pedestal"
        ),
        "negative_2d": "opaque grey clay, melted round blob, pedestal",
        "remesh_project": 0.72,
        "pbr_delta": {
            "roughness_floor": 0.05,
            "roughness_ceil": 0.40,
            "normal_strength": 0.020,
            "cavity_ao_min": 110.0,
            "ior": 1.62,
            "specularFactor": 0.98,
            "clearcoatFactor": 0.70,
            "clearcoatRoughnessFactor": 0.03,
            "transmissionFactor": 0.68,
            "attenuationDistance": 0.50,
            "attenuationColor": [0.78, 0.92, 0.99],
            "metallic_scale": 0.60,
            "multi_zone_cartography": True,
        },
    },
]

# Indices optiques continus de premiers principes (détectent tout style/matière même sans le mot "style")
_CONTINUOUS_OPTICAL_CUE_PATTERN = re.compile(
    r"\b("
    r"facett[eé]|angulaire|cis[eé]l[eé]|octogonal|prisme|"
    r"bross[eé]|brushed|stri[eé]|anisotrop|fil\s+du\s+bois|damass[eé]|martel[eé]|forg[eé]|"
    r"iris[eé]|iridescen|nacre|nacr[eé]|scarab[eé]e|holograph|dichro|opalescen|"
    r"veines?\s+d'or|kintsugi|filigrane\s+or|dorure|gold\s+inlay|liser[eé]\s+or|cloisonn[eé]|"
    r"translucide|translucent|subsurface|ambre|jade|alb[aâ]tre|opale|vitrail|cristal|"
    r"bioluminescen|incandescen|magma|lave|plasma|phosphorescen|"
    r"laqu[eé]|urushi|c[eé]ladon|[eé]maill[eé]|clearcoat|vernis\s+miroir"
    r")\b",
    flags=re.IGNORECASE,
)


def compute_continuous_optical_physics(
    prompt: str | None,
    base_pbr: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calcule par premiers principes physiques continus (équations de Fresnel, distribution
    microfacettes GGX anisotrope, loi de Beer-Lambert volumétrique, interférence de couche
    mince d'Airy et profil de dé-éclairage intrinsèque) les paramètres optiques glTF 2.0."""
    pbr = dict(base_pbr or STYLE_PROFILES["realistic_pbr"]["pbr_profile"])
    low = (prompt or "").lower()

    # 1. Loi de Fresnel en incidence normale : R0 = ((n - 1) / (n + 1))^2
    # En glTF KHR_materials_ior + KHR_materials_specular, specularFactor module F0 autour de 0.04 (IOR=1.5)
    ior = float(pbr.get("ior", 1.48))
    if re.search(r"\b(diamant|diamond)\b", low):
        ior = max(ior, 2.417)
    elif re.search(r"\b(saphir|rubis|corindon|zircon)\b", low):
        ior = max(ior, 1.77)
    elif re.search(r"\b([eé]meraude|b[eé]ryl|jade|jadeite)\b", low):
        ior = max(ior, 1.66)
    elif re.search(r"\b(glace|ice|givre)\b", low) and "cristal" not in low:
        ior = max(1.31, min(ior, 1.48))
    pbr["ior"] = round(float(ior), 4)

    fresnel_r0 = ((ior - 1.0) / (ior + 1.0)) ** 2
    derived_specular = min(1.0, max(0.15, fresnel_r0 / 0.08))
    if "specularFactor" not in pbr:
        pbr["specularFactor"] = round(derived_specular, 4)
    pbr["fresnel_r0"] = round(fresnel_r0, 5)

    # 2. Tenseur de rugosité microfacettes Beckmann / GGX anisotrope (alpha_x, alpha_y)
    r_floor = float(pbr.get("roughness_floor", 0.14))
    r_ceil = float(pbr.get("roughness_ceil", 0.95))
    r_mid = 0.5 * (r_floor + r_ceil)
    aniso = float(pbr.get("anisotropyStrength", 0.0))
    aspect = (1.0 - 0.9 * max(0.0, min(1.0, aniso))) ** 0.5
    alpha_iso = r_mid * r_mid
    pbr["ggx_alpha_x"] = round(alpha_iso / max(aspect, 1e-4), 5)
    pbr["ggx_alpha_y"] = round(alpha_iso * aspect, 5)

    # 3. Absorption volumétrique de Beer-Lambert : T(d) = exp(-sigma_a * d)
    tx = float(pbr.get("transmissionFactor", 0.0))
    if tx > 0.0:
        att_d = float(pbr.get("attenuationDistance", 0.35))
        if "attenuationColor" not in pbr:
            if any(w in low for w in ("rose", "pink", "rubis", "ruby", "magenta", "corail")):
                pbr["attenuationColor"] = [1.0, 0.48, 0.72]
            elif any(w in low for w in ("bleu", "blue", "cyan", "saphir", "sapphire", "azur")):
                pbr["attenuationColor"] = [0.38, 0.82, 1.0]
            elif any(w in low for w in ("vert", "green", "emeraude", "emerald", "jade")):
                pbr["attenuationColor"] = [0.35, 0.95, 0.62]
            elif any(w in low for w in ("ambre", "amber", "or", "gold", "jaune", "yellow")):
                pbr["attenuationColor"] = [1.0, 0.78, 0.35]
            else:
                pbr["attenuationColor"] = [0.94, 0.97, 1.0]
        att_col = list(pbr.get("attenuationColor", [0.94, 0.97, 1.0]))
        import math as _math
        sigma_a = [
            round(-_math.log(max(1e-4, min(0.9999, float(c)))) / max(att_d, 1e-3), 4)
            for c in att_col[:3]
        ]
        pbr["beer_lambert_sigma_a"] = sigma_a

    # 4. Calibrage automatique du profil de dé-éclairage intrinsèque (Intrinsic Delighting)
    outline_lock = bool(pbr.get("outline_matte_lock", False))
    style_id = str(pbr.get("style_id", "realistic_pbr"))
    is_stylized_2d = outline_lock or any(k in style_id for k in ("cartoon", "anime", "comic", "watercolor"))
    pbr["delighting_profile"] = {
        "enabled": True,
        "shadow_removal_strength": 0.58 if is_stylized_2d else 0.78,
        "specular_suppression_strength": 0.62 if is_stylized_2d else 0.84,
        "chroma_preservation": 0.92,
        "preserve_ink_outlines": outline_lock,
        "sh_order": 2,
    }
    return pbr


def _query_local_llm_style_axes(prompt: str, *, force_for_novel_style: bool = False) -> dict[str, Any] | None:
    """Interroge Ollama local par premiers principes optiques (actif par défaut sur tout style inédit
    ou lorsque `AURORA_STYLE_LLM_ENRICH=1`) avec timeout borné pour synthétiser les paramètres
    physiques continus (IOR, rugosité, clearcoat, transmission, iridescence, anisotropie)."""
    if not force_for_novel_style and os.environ.get("AURORA_STYLE_LLM_ENRICH", "1") == "0":
        return None
    ollama_url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/") + "/api/generate"
    model = os.environ.get("AURORA_STYLE_LLM_MODEL", "")
    if not model:
        try:
            from llm_disponible import resoudre_modele as _res_llm
            model = _res_llm("orcarouter/Qwen3.8-27B-Uncensored:latest", "texte", bavard=False)
        except Exception:
            model = "orcarouter/Qwen3.8-27B-Uncensored:latest"
    sys_prompt = (
        "Analyze the artistic and material style of this 3D/2D request by physical optics first principles "
        "and return ONLY a JSON object with keys: "
        "roughness_floor (0.04..0.85), roughness_ceil (0.30..0.98), normal_strength (0.008..0.030), "
        "ior (1.31..2.42), specularFactor (0.15..1.0), clearcoatFactor (0.0..0.90), "
        "transmissionFactor (0.0..0.80), attenuationDistance (0.10..2.0), "
        "iridescenceFactor (0.0..0.96), anisotropyStrength (0.0..0.85), "
        "emissiveStrength (0.0..4.0), remesh_project (0.45..0.88)."
    )
    payload = json.dumps({
        "model": model,
        "prompt": f"{sys_prompt}\nRequest: {prompt}",
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 2048},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(ollama_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parsed = json.loads(data.get("response", "{}"))
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass
    return None


def synthesize_dynamic_style_profile(prompt: str | None) -> dict[str, Any] | None:
    """Synthétise à la volée un profil de style multi-axes complet pour tout style
    nouveau, hybride ou descriptif non répertorié dans les 8 archétypes de base,
    ou enrichit un archétype existant lors d'une fusion de styles."""
    text = (prompt or "").strip()
    if not text:
        return None

    matched_descriptors = [
        desc for desc in _DYNAMIC_MATERIAL_DESCRIPTORS
        if re.search(desc["pattern"], text, flags=re.IGNORECASE)
    ]

    # Détection générique d'une expression de style explicite ("style <X>", "en <matière>", "façon <Y>")
    explicit_style_match = re.search(
        r"\b(?:style|fa[cç]on|esth[eé]tique|rendu|mat[iè]re|texture|sculpture\s+en|forg[eé]\s+en|taill[eé]\s+dans|coul[eé]\s+en)\s+([a-zA-ZÀ-ÿ0-9\s,'-]{3,45})",
        text,
        flags=re.IGNORECASE,
    )
    optical_cue_match = _CONTINUOUS_OPTICAL_CUE_PATTERN.search(text)

    if not matched_descriptors and not explicit_style_match and not optical_cue_match:
        return None

    # Base de départ : réalisme PBR haute fidélité que l'on sculpte continûment
    base_pbr = dict(STYLE_PROFILES["realistic_pbr"]["pbr_profile"])
    base_env = dict(STYLE_PROFILES["realistic_pbr"]["3d_env"])
    pos_parts: list[str] = []
    neg_parts: list[str] = []
    tags: list[str] = []
    labels: list[str] = []
    remesh_projects: list[float] = []

    for desc in matched_descriptors:
        tags.append(desc["tag"])
        labels.append(desc["label"])
        pos_parts.append(desc["positive_2d"])
        neg_parts.append(desc["negative_2d"])
        remesh_projects.append(float(desc.get("remesh_project", 0.55)))
        for k, v in desc["pbr_delta"].items():
            if k in {
                "clearcoatFactor",
                "transmissionFactor",
                "iridescenceFactor",
                "anisotropyStrength",
                "emissiveStrength",
                "metallic_scale",
                "specularFactor",
                "ior",
            } and isinstance(v, (int, float)) and isinstance(base_pbr.get(k), (int, float)):
                base_pbr[k] = max(float(base_pbr[k]), float(v))
            else:
                base_pbr[k] = v

    # Si l'utilisateur demande un style totalement inédit ("style bio-luminescent corallien martelé", etc.)
    if (explicit_style_match or optical_cue_match) and not matched_descriptors:
        custom_phrase = (
            explicit_style_match.group(1).strip(" .,;:")
            if explicit_style_match
            else optical_cue_match.group(0).strip(" .,;:")
        )
        tags.append("custom_" + re.sub(r"[^a-z0-9]+", "_", custom_phrase.lower()).strip("_")[:24])
        labels.append(f"Style Dynamique Sur-Mesure ({custom_phrase})")
        pos_parts.append(
            f"authentic {custom_phrase} artistic and material style, high geometric precision, "
            "crisp silhouette separation on pure white studio background, no pedestal"
        )
        neg_parts.append("generic plastic, blurry low-res texture, unwanted base or stand")
        remesh_projects.append(0.58)
        base_pbr["multi_zone_cartography"] = True

    # Affinage continu par analyse lexicale des propriétés optiques de premiers principes
    low = text.lower()
    if re.search(r"\b(facett[eé]|angulaire|cis[eé]l[eé]|g[eé]om[eé]trique|pli[eé]|octogonal|prisme)\b", low):
        remesh_projects.append(max(0.76, max(remesh_projects) if remesh_projects else 0.76))
    if re.search(r"\b(organique|galb[eé]|arrondi|fluide|anatomique|doux)\b", low):
        remesh_projects.append(0.48)
    if re.search(r"\b(bross[eé]|brushed|stri[eé]|anisotrop|fil\s+du\s+bois|soie|satin\s+m[eé]tal|martel[eé]|damas)\b", low):
        base_pbr["anisotropyStrength"] = max(float(base_pbr.get("anisotropyStrength", 0.0)), 0.62)
        base_pbr.setdefault("anisotropyRotation", 0.35)
    if re.search(r"\b(iris[eé]|iridescen|nacre|nacr[eé]|scarab[eé]e|holograph|arc[- ]en[- ]ciel|dichro|opalescen)\b", low):
        base_pbr["iridescenceFactor"] = max(float(base_pbr.get("iridescenceFactor", 0.0)), 0.82)
        base_pbr["iridescenceIor"] = float(base_pbr.get("iridescenceIor", 1.38))
        base_pbr.setdefault("iridescenceThicknessMinimum", 140.0)
        base_pbr.setdefault("iridescenceThicknessMaximum", 420.0)
    if re.search(r"\b(veines?\s+d'or|kintsugi|filigrane\s+or|dorure|gold\s+inlay|liser[eé]\s+or|cloisonn[eé])\b", low):
        base_pbr["vein_metallic_boost"] = True
        base_pbr["multi_zone_cartography"] = True
        base_pbr["metallic_scale"] = max(float(base_pbr.get("metallic_scale", 1.0)), 1.30)
    if re.search(r"\b(translucide|translucent|subsurface|gel[eé]e|ambre|jade|cire)\b", low):
        base_pbr["transmissionFactor"] = max(float(base_pbr.get("transmissionFactor", 0.0)), 0.45)
        base_pbr.setdefault("attenuationDistance", 0.45)
        base_pbr.setdefault("attenuationColor", [0.92, 0.86, 0.72])

    llm_axes = _query_local_llm_style_axes(text)
    if isinstance(llm_axes, dict):
        for k in (
            "roughness_floor",
            "roughness_ceil",
            "normal_strength",
            "ior",
            "specularFactor",
            "clearcoatFactor",
            "transmissionFactor",
            "attenuationDistance",
            "iridescenceFactor",
            "anisotropyStrength",
            "emissiveStrength",
        ):
            if isinstance(llm_axes.get(k), (int, float)):
                base_pbr[k] = float(llm_axes[k])
        if isinstance(llm_axes.get("remesh_project"), (int, float)):
            remesh_projects.append(float(llm_axes["remesh_project"]))

    final_remesh_proj = round(sum(remesh_projects) / max(1, len(remesh_projects)), 2) if remesh_projects else 0.55
    final_remesh_proj = max(0.42, min(0.88, final_remesh_proj))

    base_env["AURORA_TRELLIS2_REMESH"] = "1"
    base_env["AURORA_TRELLIS2_REMESH_PROJECT"] = f"{final_remesh_proj:.2f}"
    base_env["AURORA_ROUGHNESS_FLOOR"] = f"{float(base_pbr.get('roughness_floor', 0.14)):.2f}"

    style_id = "dynamic_" + "_".join(tags[:2]) if tags else "dynamic_custom_style"
    base_pbr["style_id"] = style_id
    base_pbr = compute_continuous_optical_physics(text, base_pbr)

    return {
        "style_id": style_id,
        "dynamic_synthesized": True,
        "matched_tags": tags,
        "label": " + ".join(labels) if labels else "Style Dynamique Multi-Axes",
        "2d_positive_guardrails": ", ".join(dict.fromkeys(pos_parts)),
        "2d_negative_guardrails": ", ".join(dict.fromkeys(neg_parts)),
        "3d_env": base_env,
        "pbr_profile": base_pbr,
    }


# ── Le style DEMANDÉ l'emporte sur le style déduit du sujet (15/11/2026) ─────────────────────────────
# « Zig et Sharko en version réaliste » sortait en « Cartoon 2D Franco-Belge / Xilam » : les déclencheurs
# reconnaissent le SUJET (une série animée) et imposaient son médium d'origine. Règle de l'utilisateur :
# réaliste demandé → réalisme haut de gamme ; animé demandé → animation haut de gamme ; un personnage
# animé « en version réaliste » → réaliste. Le médium vient du contrat de demande (`style.cible`, lu
# par le modèle de langue sur les mots exacts) et n'est appliqué que s'il contredit la famille déduite.
FAMILLES_STYLE = {
    "realistic_pbr": "realiste", "crystal_glossy": "realiste",
    "cartoon_2d_flat": "2d", "anime_cel": "2d", "comic_manga_ink": "2d",
    "figurine_collector": "figurine", "voxel_cubic": "figurine", "clay_stopmotion": "figurine",
}
FAMILLE_DE_CIBLE = {"photo": "realiste", "cel_2d": "2d", "figurine": "figurine", "cgi_3d": "animation_3d"}


def _profil_archetype(style_id: str, texte: str) -> dict[str, Any]:
    prof = STYLE_PROFILES[style_id]
    return {"style_id": style_id, **prof, "3d_env": dict(prof["3d_env"]),
            "pbr_profile": compute_continuous_optical_physics(texte, dict(prof["pbr_profile"]))}


def aligner_sur_cible(profil: dict[str, Any], cible: str | None, texte: str = "") -> dict[str, Any]:
    """Profil de style conforme au médium demandé ; inchangé sans demande explicite ou s'il y est déjà conforme."""
    voulu = FAMILLE_DE_CIBLE.get(cible or "")
    if voulu is None:
        return profil
    famille = FAMILLES_STYLE.get(str(profil.get("style_id", "")).split("__")[0], "dynamique")
    if voulu == "animation_3d":
        if famille not in ("realiste", "2d"):
            return profil
        nouveau = classify_style("rendu de long métrage d'animation 3D haut de gamme, style Pixar")
    elif famille == voulu:
        return profil
    else:
        nouveau = _profil_archetype({"realiste": "realistic_pbr", "2d": "anime_cel", "figurine": "figurine_collector"}[voulu],
                                    texte)
    nouveau = dict(nouveau)
    nouveau["impose_par_la_demande"] = {"cible": cible, "remplace": profil.get("style_id")}
    return nouveau


def classify_style(prompt: str | None) -> dict[str, Any]:
    """Identifie la famille de style d'une requête (2D ou 3D) ou synthétise à la volée
    un profil multi-axes sur-mesure pour tout style inédit ou hybride."""
    text = re.sub(r"[_]+", " ", (prompt or "")).strip()
    dyn = synthesize_dynamic_style_profile(text)

    # Vérifier d'abord les 7 archétypes spécifiques avant realistic_pbr
    for style_id in _PRIORITY_ORDER:
        prof = STYLE_PROFILES[style_id]
        if style_id == "realistic_pbr":
            break
        if re.search(prof["triggers"], text, flags=re.IGNORECASE):
            out = {
                "style_id": style_id,
                **prof,
                "3d_env": dict(prof["3d_env"]),
                "pbr_profile": compute_continuous_optical_physics(text, dict(prof["pbr_profile"])),
            }
            # Si le prompt combine un archétype (ex: figurine / anime) avec une matière/style dynamique
            # (ex: "figurine en porcelaine kintsugi" ou "anime en vitrail gothique"), fusionner !
            if dyn is not None and dyn.get("matched_tags"):
                base_arch_pbr = dict(prof["pbr_profile"])
                out["pbr_profile"].update(dyn["pbr_profile"])
                if style_id in {"anime_cel", "cartoon_2d_flat"}:
                    out["pbr_profile"]["roughness_floor"] = max(
                        0.32,
                        0.5 * float(base_arch_pbr.get("roughness_floor", 0.64))
                        + 0.5 * float(dyn["pbr_profile"].get("roughness_floor", 0.14)),
                    )
                    out["pbr_profile"]["metallic_scale"] = min(
                        float(out["pbr_profile"].get("metallic_scale", 1.0)), 0.85
                    )
                out["pbr_profile"]["style_id"] = f"{style_id}__{dyn['style_id']}"
                out["pbr_profile"] = compute_continuous_optical_physics(text, out["pbr_profile"])
                out["3d_env"]["AURORA_TRELLIS2_REMESH_PROJECT"] = dyn["3d_env"]["AURORA_TRELLIS2_REMESH_PROJECT"]
                out["3d_env"]["AURORA_ROUGHNESS_FLOOR"] = f"{float(out['pbr_profile'].get('roughness_floor', 0.20)):.2f}"
                out["2d_positive_guardrails"] = f"{out['2d_positive_guardrails']}, {dyn['2d_positive_guardrails']}"
                out["hybrid_dynamic_tags"] = dyn["matched_tags"]
            return out

    if dyn is not None:
        return dyn

    return {
        "style_id": "realistic_pbr",
        **STYLE_PROFILES["realistic_pbr"],
        "3d_env": dict(STYLE_PROFILES["realistic_pbr"]["3d_env"]),
        "pbr_profile": compute_continuous_optical_physics(
            text, dict(STYLE_PROFILES["realistic_pbr"]["pbr_profile"])
        ),
    }


def resolve_pbr_optical_profile(prompt: str | None) -> dict[str, Any]:
    """Fusionne le profil PBR du style (archétype ou synthétisé dynamiquement) avec toute
    demande explicite de modification de matière, brillance, anisotropie, iridescence
    ou finition optique dans le prompt."""
    style = classify_style(prompt)
    pbr = dict(style.get("pbr_profile") or STYLE_PROFILES["realistic_pbr"]["pbr_profile"])
    pbr["style_id"] = style.get("style_id", "realistic_pbr")
    pbr.setdefault("multi_zone_cartography", True)
    low = (prompt or "").lower()

    has_glazed_or_clearcoat = bool(
        re.search(
            r"\b(kintsugi|porcelaine|porcelain|c[eé]ramique|ceramic|[eé]mail|vitrail|cristal|verre|vernis|laqu[eé]|glossy|clearcoat|nacre|chitine|urushi|c[eé]ladon|ambre|jade)\b",
            low,
        )
    )
    if re.search(r"\b(mat|matte|satin[eé]\s+mat|velours|feutrine|craie|pl[aâ]tre)\b", low) and not has_glazed_or_clearcoat:
        pbr["roughness_floor"] = max(float(pbr.get("roughness_floor", 0.65)), 0.72)
        pbr["roughness_ceil"] = 0.98
        pbr["specularFactor"] = min(float(pbr.get("specularFactor", 0.35)), 0.25)
        pbr["clearcoatFactor"] = 0.0
    elif re.search(r"\b(vernis|laqu[eé]|glossy|brillant|mouill[eé]|wet|carrosserie|clearcoat|[eé]maill[eé]|urushi|c[eé]ladon)\b", low):
        pbr["roughness_floor"] = min(float(pbr.get("roughness_floor", 0.14)), 0.08)
        pbr["specularFactor"] = max(float(pbr.get("specularFactor", 0.85)), 0.92)
        pbr["clearcoatFactor"] = max(float(pbr.get("clearcoatFactor", 0.0)), 0.55)
        pbr["clearcoatRoughnessFactor"] = 0.03

    if re.search(r"\b(chrome|or\s+massif|or\s+pur|gold|argent\s+poli|acier\s+poli|cuivre\s+poli|laiton|m[eé]tallique|damas|titane)\b", low):
        pbr["roughness_floor"] = min(float(pbr.get("roughness_floor", 0.12)), 0.09)
        pbr["metallic_scale"] = max(float(pbr.get("metallic_scale", 1.0)), 1.25)
        pbr["specularFactor"] = 1.0
        pbr["vein_metallic_boost"] = True

    if re.search(r"\b(n[eé]on|bioluminescen|glow|lueur|[eé]missif|emissive|plasma|laser|holograph|incandescen|magma|lave)\b", low):
        pbr["emissiveStrength"] = max(float(pbr.get("emissiveStrength", 1.0)), 2.5)

    return compute_continuous_optical_physics(prompt, pbr)


# ==============================================================================
# DÉ-ÉCLAIRAGE INTRINSÈQUE D'ALBÉDO (MULTI-VIEW & SINGLE-ATLAS INTRINSIC DELIGHTING)
# Décomposition physique I(x) = R(x) * S(x) + H(x) par Harmoniques Sphériques d'ordre 2
# (Ramamoorthi & Hanrahan, 9 bases) + Retinex multi-échelles guidé par la chromaticité
# pour retirer les ombres portées/propres cuites et les reflets spéculaires figés avant
# le relighting PBR dynamique, tout en préservant à 100 % les pigments et traits d'encre.
# ==============================================================================


def _srgb_to_linear(srgb_01: "Any") -> "Any":
    import numpy as np
    x = np.clip(np.asarray(srgb_01, dtype=np.float32), 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def _linear_to_srgb(lin_01: "Any") -> "Any":
    import numpy as np
    x = np.clip(np.asarray(lin_01, dtype=np.float32), 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * (np.maximum(x, 1e-8) ** (1.0 / 2.4)) - 0.055).astype(np.float32)


def _gaussian_smooth_2d(field: "Any", sigma: float) -> "Any":
    import numpy as np
    arr = np.asarray(field, dtype=np.float32)
    if sigma <= 0.15:
        return arr
    try:
        import cv2
        return cv2.GaussianBlur(arr, (0, 0), float(sigma))
    except Exception:
        from scipy.ndimage import gaussian_filter
        if arr.ndim == 2:
            return gaussian_filter(arr, sigma=float(sigma))
        return gaussian_filter(arr, sigma=(float(sigma), float(sigma), 0.0))


def estimate_spherical_harmonics_irradiance(
    albedo_rgb: "Any",
    normals_xyz: "Any | None" = None,
    valid_mask: "Any | None" = None,
) -> tuple["Any", "Any"]:
    """Estime le champ d'éclairement basse fréquence cuit dans l'albédo par projection
    sur les 9 fonctions de base d'Harmoniques Sphériques réelles d'ordre 2 ($l \\le 2$,
    Ramamoorthi & Hanrahan).

    Retourne `(sh_shading_field, sh_coeffs)` où `sh_shading_field` est le facteur
    d'illumination normalisé autour de `1.0` de dimension `(H, W)` et `sh_coeffs` est
    le vecteur de 9 coefficients SH.
    """
    import numpy as np

    rgb = np.asarray(albedo_rgb, dtype=np.float32)
    if rgb.max() > 1.05:
        rgb = rgb / 255.0
    lin = _srgb_to_linear(rgb)
    h, w = lin.shape[:2]
    luma = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]

    if normals_xyz is not None:
        nrm = np.asarray(normals_xyz, dtype=np.float32)
        if nrm.shape[:2] != (h, w):
            nrm = np.broadcast_to(nrm, (h, w, 3)).copy()
    else:
        # Reconstruction de pseudo-normales basses fréquences à partir du relief de luminance lissé
        sigma_n = max(2.0, min(h, w) * 0.035)
        l_smooth = _gaussian_smooth_2d(luma, sigma_n)
        gy, gx = np.gradient(l_smooth)
        nx = -gx * 4.5
        ny = -gy * 4.5
        nz = np.ones_like(l_smooth, dtype=np.float32)
        nrm = np.stack([nx, ny, nz], axis=-1)

    n_len = np.sqrt(np.sum(nrm * nrm, axis=-1, keepdims=True) + 1e-8)
    nx = nrm[..., 0] / n_len[..., 0]
    ny = nrm[..., 1] / n_len[..., 0]
    nz = nrm[..., 2] / n_len[..., 0]

    # Les 9 bases réelles d'Harmoniques Sphériques d'irradiance Lambertienne (l = 0, 1, 2)
    y00 = np.full_like(nx, 0.282095, dtype=np.float32)
    y1_1 = 0.488603 * ny
    y10 = 0.488603 * nz
    y11 = 0.488603 * nx
    y2_2 = 1.092548 * nx * ny
    y2_1 = 1.092548 * ny * nz
    y20 = 0.315392 * (3.0 * nz * nz - 1.0)
    y21 = 1.092548 * nx * nz
    y22 = 0.546274 * (nx * nx - ny * ny)
    basis = np.stack([y00, y1_1, y10, y11, y2_2, y2_1, y20, y21, y22], axis=-1)  # (H, W, 9)

    # Pondération robuste : exclure les contours d'encre noirs (luma < 0.03) et les saturations spéculaires (> 0.94)
    sat = (np.max(lin, axis=-1) - np.min(lin, axis=-1)) / (np.max(lin, axis=-1) + 1e-4)
    weights = np.ones((h, w), dtype=np.float32)
    if valid_mask is not None:
        weights *= (np.asarray(valid_mask) > 0).astype(np.float32)
    weights *= np.clip((luma - 0.025) / 0.08, 0.0, 1.0)
    weights *= np.clip((0.96 - luma * (1.0 - 0.5 * sat)) / 0.12, 0.0, 1.0)

    log_luma = np.log(np.maximum(luma, 1e-3))
    b_flat = basis.reshape(-1, 9)
    w_flat = weights.ravel()
    y_flat = log_luma.ravel()

    # Résolution moindre carrés pondérés avec régularisation de Tikhonov sur les ordres l=1,2
    bw = b_flat * w_flat[:, None]
    ata = bw.T @ b_flat
    reg = np.diag(np.array([1e-4, 0.15, 0.15, 0.15, 0.45, 0.45, 0.45, 0.45, 0.45], dtype=np.float32) * max(1.0, float(w_flat.sum()) * 1e-3))
    rhs = bw.T @ y_flat
    try:
        sh_coeffs = np.linalg.solve(ata + reg, rhs).astype(np.float32)
    except np.linalg.LinAlgError:
        sh_coeffs = np.zeros(9, dtype=np.float32)

    log_sh = (b_flat @ sh_coeffs).reshape(h, w)
    # Normaliser autour du quantile diffus éclairé (Q78) pour que l'hémisphère ombragé ait sh_shading < 1.0
    valid_sel = w_flat > 0.1
    ref_illum = float(np.quantile(log_sh.ravel()[valid_sel], 0.78)) if np.any(valid_sel) else float(np.quantile(log_sh, 0.78))
    sh_shading = np.exp(np.clip(log_sh - ref_illum, -0.85, 0.45)).astype(np.float32)
    return sh_shading, sh_coeffs


def delight_intrinsic_albedo(
    albedo_rgb: "Any",
    normals_xyz: "Any | None" = None,
    ambient_occlusion: "Any | None" = None,
    valid_mask: "Any | None" = None,
    seam_fade: "Any | None" = None,
    style_profile: dict[str, Any] | str | None = None,
    *,
    return_decomposition: bool = False,
) -> "Any":
    """Dé-éclairage intrinsèque d'albédo (Intrinsic Delighting) par décomposition physique
    $I(\\mathbf{x}) = R(\\mathbf{x}) \\cdot S(\\mathbf{x}) + H(\\mathbf{x})$.

    Retire :
    1. Les ombres portées et ombres propres cuites ($S(\\mathbf{x}) < 1$) identifiées par
       invariance de chromaticité normalisée $\\boldsymbol{\\chi}(\\mathbf{x})$, Retinex
       multi-échelles et éclairement d'Harmoniques Sphériques d'ordre 2, sans jamais
       altérer les traits d'encre noirs ni les pigments sombres légitimes.
    2. Les taches de reflets spéculaires diélectriques cuits ($H(\\mathbf{x}) > 0$) où la
       luminance sature localement avec chute de saturation au sein d'une zone de
       chromaticité homogène.
    """
    import numpy as np

    raw = np.asarray(albedo_rgb)
    input_is_uint8 = raw.dtype == np.uint8 or float(raw.max()) > 1.05
    rgb_01 = np.clip(raw.astype(np.float32) / (255.0 if input_is_uint8 else 1.0), 0.0, 1.0)
    h, w = rgb_01.shape[:2]

    if isinstance(style_profile, str):
        pbr_prof = resolve_pbr_optical_profile(style_profile)
    elif isinstance(style_profile, dict):
        pbr_prof = style_profile.get("pbr_profile", style_profile)
    else:
        pbr_prof = resolve_pbr_optical_profile(None)

    delight_cfg = pbr_prof.get("delighting_profile") or {}
    shadow_strength = float(delight_cfg.get("shadow_removal_strength", 0.75))
    spec_strength = float(delight_cfg.get("specular_suppression_strength", 0.80))
    preserve_outlines = bool(delight_cfg.get("preserve_ink_outlines", pbr_prof.get("outline_matte_lock", False)))

    lin = _srgb_to_linear(rgb_01)
    luma = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    sum_rgb = lin[..., 0] + lin[..., 1] + lin[..., 2] + 1e-5
    chroma = lin / sum_rgb[..., None]

    # 1. Gradient de chromaticité : faible dans une ombre portée sur un même matériau,
    # élevé aux frontières de pigments / matériaux.
    gx_c = np.zeros_like(luma)
    gy_c = np.zeros_like(luma)
    for c_idx in range(3):
        cy, cx = np.gradient(chroma[..., c_idx])
        gx_c += cx * cx
        gy_c += cy * cy
    chroma_grad = np.sqrt(gx_c + gy_c)
    # Poids d'homogénéité chromatique : 1.0 si même pigment, -> 0 aux frontières de couleur
    chroma_homogeneity = np.exp(-chroma_grad * 14.0).astype(np.float32)

    # 2. Protection stricte des traits d'encre, pupilles et pigments noirs profonds
    min_dim = max(8, min(h, w))
    luma_local_bg = _gaussian_smooth_2d(luma, max(2.0, min_dim * 0.025))
    # Un trait d'encre ou pigment noir intentionnel a une luminance absolue très basse
    ink_or_dark_pigment = np.clip((0.045 - luma) / 0.035, 0.0, 1.0)
    if preserve_outlines:
        stroke_contrast = np.clip((luma_local_bg - luma - 0.14) / 0.12, 0.0, 1.0) * np.clip((0.12 - luma) / 0.08, 0.0, 1.0)
        ink_or_dark_pigment = np.maximum(ink_or_dark_pigment, stroke_contrast)

    # Protection des veines d'or / conducteurs métalliques brillants pour ne pas ternir leur éclat
    is_gold_or_metal_vein = (
        (rgb_01[..., 0] > 0.72)
        & (rgb_01[..., 1] > 0.55)
        & (rgb_01[..., 2] < 0.35)
        & ((rgb_01[..., 0] - rgb_01[..., 2]) > 0.38)
    ).astype(np.float32)

    # 3. Estimation de l'enveloppe d'illumination Retinex multi-échelles + Harmoniques Sphériques
    s1 = _gaussian_smooth_2d(luma, max(2.5, min_dim * 0.03))
    s2 = _gaussian_smooth_2d(luma, max(6.0, min_dim * 0.08))
    s3 = _gaussian_smooth_2d(luma, max(14.0, min_dim * 0.18))
    s4 = _gaussian_smooth_2d(luma, max(28.0, min_dim * 0.38))
    # Enveloppe supérieure douce (représente l'éclairement incident hors ombre locale et hémisphérique)
    illum_envelope = np.maximum(luma, np.maximum(0.30 * s1 + 0.30 * s2 + 0.40 * s3, s4 * 1.08))
    retinex_shading = np.clip(luma / np.maximum(illum_envelope, 1e-4), 0.22, 1.35)

    sh_shading, sh_coeffs = estimate_spherical_harmonics_irradiance(rgb_01, normals_xyz=normals_xyz, valid_mask=valid_mask)
    sh_clamped = np.clip(sh_shading, 0.35, 1.35)

    composite_shading = (
        0.50 * np.minimum(retinex_shading, sh_clamped)
        + 0.30 * retinex_shading
        + 0.20 * sh_clamped
    ).astype(np.float32)
    if ambient_occlusion is not None:
        ao_arr = np.asarray(ambient_occlusion, dtype=np.float32)
        if ao_arr.max() > 1.05:
            ao_arr = ao_arr / 255.0
        if ao_arr.shape[:2] == (h, w):
            composite_shading = 0.75 * composite_shading + 0.25 * np.clip(ao_arr, 0.25, 1.0)

    # 4. Dé-éclairage des ombres cuites (Shadow Lifting avec restauration de chromaticité)
    shadow_deficit = np.clip(1.0 - composite_shading, 0.0, 0.72)
    # Ne relever l'ombre que là où la chromaticité est cohérente et hors traits d'encre noirs
    effective_shadow_mask = (
        chroma_homogeneity
        * (1.0 - ink_or_dark_pigment)
        * (1.0 - 0.85 * is_gold_or_metal_vein)
    )
    if seam_fade is not None and np.asarray(seam_fade).shape[:2] == (h, w):
        sf = np.clip(np.asarray(seam_fade, dtype=np.float32), 0.0, 1.0)
        effective_shadow_mask *= sf
    if valid_mask is not None and np.asarray(valid_mask).shape[:2] == (h, w):
        effective_shadow_mask *= (np.asarray(valid_mask) > 0).astype(np.float32)

    # Gain multiplicatif inverse borné pour retirer l'ombre cuite sans brûler ni bruiter
    shadow_gain = 1.0 / np.maximum(1.0 - shadow_strength * shadow_deficit * effective_shadow_mask, 0.36)
    shadow_gain = np.clip(shadow_gain, 1.0, 2.45)

    # Chromaticité environnante lissée pour éviter la dérive grise/froide dans les ombres relevées
    chroma_neighborhood = _gaussian_smooth_2d(chroma, max(2.0, min_dim * 0.025))
    chroma_norm = chroma_neighborhood / np.maximum(np.sum(chroma_neighborhood, axis=-1, keepdims=True), 1e-5)
    blend_chroma = np.clip(0.35 * shadow_deficit * effective_shadow_mask, 0.0, 0.35)[..., None]
    restored_chroma = (1.0 - blend_chroma) * chroma + blend_chroma * chroma_norm

    luma_delighted = luma * shadow_gain
    lin_delighted = restored_chroma * (luma_delighted / np.maximum(0.2126 * restored_chroma[..., 0] + 0.7152 * restored_chroma[..., 1] + 0.0722 * restored_chroma[..., 2], 1e-4))[..., None]

    # 5. Suppression des reflets spéculaires diélectriques cuits (Specular Highlight Removal)
    sat_cur = (np.max(lin_delighted, axis=-1) - np.min(lin_delighted, axis=-1)) / (np.max(lin_delighted, axis=-1) + 1e-4)
    sigma_broad = max(10.0, min_dim * 0.16)
    sat_local = np.maximum(
        _gaussian_smooth_2d(sat_cur, max(3.0, min_dim * 0.04)),
        _gaussian_smooth_2d(sat_cur, sigma_broad),
    )
    luma_med = np.minimum(
        _gaussian_smooth_2d(luma_delighted, max(3.5, min_dim * 0.045)),
        _gaussian_smooth_2d(luma_delighted, sigma_broad),
    )
    chroma_broad = _gaussian_smooth_2d(chroma, sigma_broad)
    chroma_broad_norm = chroma_broad / np.maximum(np.sum(chroma_broad, axis=-1, keepdims=True), 1e-5)

    # Un reflet spéculaire cuit sur un diélectrique coloré présente un pic de luminance (> luma_med)
    # accompagné d'une chute locale de saturation (désaturation vers le blanc de la source lumineuse)
    luma_spike = np.clip((luma_delighted - np.maximum(luma_med * 1.12, 0.24)) / 0.28, 0.0, 1.0)
    desat_drop = np.clip((sat_local - sat_cur + 0.05) / 0.22, 0.0, 1.0)
    specular_mask = (
        luma_spike
        * desat_drop
        * (1.0 - is_gold_or_metal_vein)
        * (1.0 - ink_or_dark_pigment)
        * spec_strength
    )
    if seam_fade is not None and np.asarray(seam_fade).shape[:2] == (h, w):
        specular_mask *= np.clip(np.asarray(seam_fade, dtype=np.float32), 0.0, 1.0)
    if valid_mask is not None and np.asarray(valid_mask).shape[:2] == (h, w):
        specular_mask *= (np.asarray(valid_mask) > 0).astype(np.float32)

    diffuse_target_lin = chroma_broad_norm * (
        luma_med / np.maximum(0.2126 * chroma_broad_norm[..., 0] + 0.7152 * chroma_broad_norm[..., 1] + 0.0722 * chroma_broad_norm[..., 2], 1e-4)
    )[..., None]
    specular_residual = np.maximum(0.0, luma_delighted - luma_med) * specular_mask
    lin_final = np.clip(
        (1.0 - specular_mask[..., None]) * lin_delighted + specular_mask[..., None] * diffuse_target_lin,
        0.0,
        1.0,
    )
    lin_final = (1.0 - ink_or_dark_pigment[..., None]) * lin_final + ink_or_dark_pigment[..., None] * lin

    srgb_final = _linear_to_srgb(lin_final)
    out_arr = np.round(srgb_final * 255.0).astype(np.uint8) if input_is_uint8 else srgb_final

    if not return_decomposition:
        return out_arr

    shadow_before = float(np.std(luma))
    luma_after = 0.2126 * lin_final[..., 0] + 0.7152 * lin_final[..., 1] + 0.0722 * lin_final[..., 2]
    shadow_after = float(np.std(luma_after))
    return out_arr, {
        "shading_map": composite_shading,
        "sh_shading_map": sh_shading,
        "sh_coeffs": sh_coeffs.tolist(),
        "shadow_gain_map": shadow_gain,
        "specular_residual": specular_residual,
        "luma_std_before": round(shadow_before, 5),
        "luma_std_after": round(shadow_after, 5),
        "mean_shadow_gain": round(float(shadow_gain.mean()), 4),
        "max_specular_suppressed": round(float(specular_residual.max()), 4),
    }


def delight_multi_view_albedo(
    views_rgb: "Any",
    view_normals: "Any | None" = None,
    view_weights: "Any | None" = None,
    style_profile: dict[str, Any] | str | None = None,
    *,
    return_decomposition: bool = False,
) -> "Any":
    """Dé-éclairage intrinsèque multi-vues (Multi-View Intrinsic Albedo Delighting).

    Fusionne $V \\ge 2$ projections ou vues d'une texture $(V, H, W, 3)$ en rejetant :
    - la queue inférieure d'ombrage directionnel propre à une vue (ombres portées),
    - la queue supérieure de spécularité dépendante de l'angle de vue $(\\mathbf{n} \\cdot \\mathbf{v}_v)$,
    puis applique la décomposition intrinsèque `delight_intrinsic_albedo` sur l'albédo consensuel.
    """
    import numpy as np

    stack = np.asarray(views_rgb)
    if stack.ndim == 3:
        return delight_intrinsic_albedo(
            stack,
            normals_xyz=view_normals,
            style_profile=style_profile,
            return_decomposition=return_decomposition,
        )
    if stack.ndim != 4 or stack.shape[0] == 0:
        raise ValueError("views_rgb must have shape (V, H, W, 3) or (H, W, 3)")

    input_is_uint8 = stack.dtype == np.uint8 or float(stack.max()) > 1.05
    stack_01 = np.clip(stack.astype(np.float32) / (255.0 if input_is_uint8 else 1.0), 0.0, 1.0)
    n_views, h, w, _ = stack_01.shape
    lin_stack = _srgb_to_linear(stack_01)
    luma_stack = 0.2126 * lin_stack[..., 0] + 0.7152 * lin_stack[..., 1] + 0.0722 * lin_stack[..., 2]

    # Pondération angulaire et réjection statistique des queues (ombres < Q25, reflets > Q80)
    q_low = np.quantile(luma_stack, 0.25 if n_views >= 3 else 0.35, axis=0, keepdims=True)
    q_high = np.quantile(luma_stack, 0.80 if n_views >= 3 else 0.75, axis=0, keepdims=True)
    q_med = np.median(luma_stack, axis=0, keepdims=True)

    # Poids gaussien centré sur le quantile diffus médian-haut (sans ombre portée ni pic spéculaire)
    target_luma = 0.65 * q_med + 0.35 * q_high
    sigma_l = np.maximum(q_high - q_low, 0.06)
    w_stat = np.exp(-0.5 * ((luma_stack - target_luma) / sigma_l) ** 2).astype(np.float32)
    # Pénaliser fortement les ombres portées sombres (luma < q_low) et les reflets saturés (luma > q_high * 1.15)
    w_stat *= np.where(luma_stack < q_low * 0.92, 0.15, 1.0).astype(np.float32)
    w_stat *= np.where(luma_stack > np.maximum(q_high * 1.12, 0.85), 0.12, 1.0).astype(np.float32)

    if view_weights is not None:
        vw = np.asarray(view_weights, dtype=np.float32)
        if vw.shape == (n_views, h, w):
            w_stat *= np.maximum(vw, 1e-4)
        elif vw.shape == (n_views,):
            w_stat *= np.maximum(vw[:, None, None], 1e-4)

    w_sum = np.maximum(np.sum(w_stat, axis=0, keepdims=True), 1e-6)
    fused_lin = np.sum(lin_stack * (w_stat[..., None] / w_sum[..., None]), axis=0)
    fused_srgb = _linear_to_srgb(fused_lin)
    fused_input = np.round(fused_srgb * 255.0).astype(np.uint8) if input_is_uint8 else fused_srgb

    avg_normals = None
    if view_normals is not None:
        vn = np.asarray(view_normals, dtype=np.float32)
        if vn.ndim == 4 and vn.shape[0] == n_views:
            avg_normals = np.sum(vn * (w_stat[..., None] / w_sum[..., None]), axis=0)
        elif vn.ndim == 3:
            avg_normals = vn

    res = delight_intrinsic_albedo(
        fused_input,
        normals_xyz=avg_normals,
        style_profile=style_profile,
        return_decomposition=return_decomposition,
    )
    if not return_decomposition:
        return res
    delighted_img, info = res
    info["multi_view_count"] = int(n_views)
    info["multi_view_variance_before"] = round(float(np.mean(np.var(luma_stack, axis=0))), 6)
    return delighted_img, info

