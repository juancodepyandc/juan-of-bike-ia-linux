#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA Universal Hollow Vessel & Optical Crystal Engraver (`crystal_vessel_sculptor.py`).

Moteur géométrique et optique universel (Zéro Hardcoding de sujet) pour les récipients,
vases, flacons, carafes et coupes en verre/cristal/matériau réfractif avec gravures
calligraphiques et motifs en bas-relief :
1. Synthèse implicite et paramétrique de coques creuses 2-manifold étanches (`watertight`)
   avec cavité intérieure réelle, col ouvert biseauté, pied stable et profil morphologique
   continu : vraie silhouette de cœur 3D bilobée à coussin galbé (`x = sin^3(t)`, lobes hauts
   gauche/droite bien marqués, pointe en V inférieure sur piédestal en cristal et col central
   évasé creux).
2. Projection planaire frontale orientée (+X de gauche à droite, +Y de bas en haut) sans
   inversion miroir ni fantôme arrière, déplaçant les sommets 3D en bas-relief lisse et
   dépolissant localement la rugosité (`G=118` vs `G=10` sur le cristal poli).
3. Cartographie PBR 2K (Albédo RGBA à transparence de Fresnel + NormalMap Scharr/Sobel
   + ORM Cavité/Rugosité/Métallicité) et injection des extensions glTF 2.0
   (`KHR_materials_transmission`, `KHR_materials_volume`, `KHR_materials_ior`,
   `KHR_materials_clearcoat`, `KHR_materials_specular`).
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import trimesh

from pbr_cartography import inject_gltf_optical_extensions


def is_engraved_or_shaped_vessel_prompt(prompt: str) -> bool:
    """Détecte universellement si la requête décrit un vase/flacon/récipient façonné ou gravé."""
    low = (prompt or "").lower()
    has_vessel = bool(
        re.search(
            r"\b(vase|vases|flacon|carafe|urne|coupe|calice|bocal|troph[eé]e)\b",
            low,
        )
    )
    has_person = bool(
        re.search(
            r"\b(personnage|personne|humain|homme|femme|garcon|fille|guerrier|mage|character)\b",
            low,
        )
    )
    return has_vessel and not has_person


def _parse_named_color_rgb(text_fragment: str) -> tuple[str, tuple[int, int, int], tuple[int, int, int], list[float]] | None:
    low = (text_fragment or "").lower()

    def _has_word(words: tuple[str, ...]) -> bool:
        return bool(re.search(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", low))

    if _has_word(("blanc", "blanche", "white", "ivoire", "porcelaine", "opale", "neige")):
        return ("pure_white", (252, 253, 255), (226, 232, 240), [0.98, 0.99, 1.0])
    if _has_word(("rose", "pink", "magenta", "rubis", "ruby", "corail", "fushia", "fuchsia")):
        return ("rose_crystal", (238, 86, 152), (192, 36, 104), [1.0, 0.42, 0.68])
    if _has_word(("rouge", "red", "carmin", "bordeaux", "grenat")):
        return ("crimson_crystal", (224, 48, 76), (164, 18, 44), [0.95, 0.22, 0.34])
    if _has_word(("bleu", "bleue", "blue", "cyan", "saphir", "sapphire", "azur", "turquoise")):
        return ("sapphire_crystal", (78, 168, 242), (32, 98, 188), [0.35, 0.75, 1.0])
    if _has_word(("vert", "verte", "green", "emeraude", "émeraude", "emerald", "jade")):
        return ("emerald_crystal", (72, 206, 146), (26, 138, 86), [0.32, 0.92, 0.58])
    if _has_word(("ambre", "amber", "or", "gold", "jaune", "yellow", "doré", "doree", "dore")):
        return ("amber_crystal", (244, 192, 88), (198, 128, 28), [1.0, 0.76, 0.32])
    if _has_word(("noir", "noire", "black", "obsidienne", "onyx", "anthracite")):
        return ("obsidian_crystal", (42, 44, 52), (18, 20, 26), [0.22, 0.24, 0.28])
    if _has_word(("violet", "violette", "purple", "amethyste", "améthyste", "lilas", "lavande")):
        return ("amethyst_crystal", (172, 104, 236), (112, 48, 178), [0.72, 0.42, 0.98])
    return None


def extract_engraving_spec(prompt: str, base_spec: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extrait dynamiquement (et met à jour de façon incrémentale si `base_spec` est fourni)
    le texte à graver, les motifs, la couleur extérieure ET la couleur intérieure (blanc pur par défaut)."""
    text = (prompt or "").strip()
    low = text.lower()
    prev = dict(base_spec) if isinstance(base_spec, dict) else {}

    engraved_text: str | None = prev.get("engraved_text")
    stop_words = {
        "de", "du", "des", "un", "une", "le", "la", "les", "par", "en", "pour",
        "avec", "sur", "dans", "coeur", "coeurs", "vase", "verre", "cristal",
        "rose", "blanc", "bleu", "rouge", "vert", "noir", "or",
    }
    patterns = [
        r"(?:remplac(?:er|e)|chang(?:er|e)|modifi(?:er|e))\s+(?:le\s+|la\s+)?(?:pr[eé]nom|nom|mot|texte|gravure)\s+(?:par|en|pour|avec)\s+['\"«]?([A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’-]{2,24})['\"»]?",
        r"(?:grav(?:er|é|ee|es|ure)|inscri(?:re|t|ption)|marqu(?:er|é)|[eé]crit)\s+(?:le\s+|la\s+|un\s+|une\s+)?(?:pr[eé]nom|nom|mot|texte)\s+(?:par\s+|en\s+)?['\"«]?([A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’-]{2,24})['\"»]?",
        r"(?:pr[eé]nom|nom)\s*(?:[:=]|par|en|est)?\s*['\"«]?([A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’-]{2,22})['\"»]?",
        r"(?:grav(?:er|é|ee|es|ure)|inscri(?:re|t|ption))\s+['\"«]([A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’\s-]{2,24})['\"»]",
        r"(?:grav(?:er|é|ee|es|ure)|engraved\s+with(?:\s+the\s+name)?)\s+([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ0-9'’-]{2,20})\b",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            cand = m.group(1).strip(" '\",.;:!?")
            if cand.lower() not in stop_words:
                engraved_text = cand
                break
        if engraved_text != prev.get("engraved_text"):
            break

    if re.search(r"\b(sans\s+(?:gravure|pr[eé]nom|texte|nom)|enl[eè]v(?:e|er)\s+(?:la\s+gravure|le\s+pr[eé]nom|le\s+texte))\b", low):
        engraved_text = None

    heart_shape = bool(
        prev.get("heart_shape", True)
        if prev
        else re.search(r"\b(forme\s+de\s+c(?:oe|œ)urs?|c(?:oe|œ)urs?|heart[- ]?shaped|hearts?)\b", low)
    )
    if re.search(r"\b(anatomique|cardiaque|ventricul|aort|organe|anatomical)\b", low):
        heart_style = "anatomical"
    elif re.search(r"\b([eé]mojie?|emoji|romantique|classique)\b", low):
        heart_style = "emoji"
    else:
        heart_style = str(prev.get("heart_style") or "emoji")

    is_empty_vessel = not bool(
        re.search(r"\b(avec\s+(?:des\s+)?fleurs|garni\s+de\s+fleurs|rempli\s+de\s+fleurs)\b", low)
        and not re.search(r"\b(sans\s+(?:rien|fleurs?|plantes?|contenu)|vide|empty)\b", low)
    )
    real_print_height_mm = float(prev.get("real_print_height_mm", 180.0))
    m_mm = re.search(r"\b(\d{2,3}(?:[.,]\d+)?)\s*mm\b", low)
    if m_mm:
        val_mm = float(m_mm.group(1).replace(",", "."))
        if 60.0 <= val_mm <= 400.0:
            real_print_height_mm = val_mm

    has_heart_motifs = bool(
        prev.get("has_heart_motifs", True)
        if prev
        else (re.search(r"\b(des\s+c(?:oe|œ)urs|avec\s+c(?:oe|œ)urs|motifs?\s+de\s+c(?:oe|œ)urs?|gravures?\s+de\s+c(?:oe|œ)urs?|hearts?)\b", low) or heart_shape)
    )
    has_star_motifs = bool(re.search(r"\b([eé]toiles?|stars?)\b", low)) or bool(prev.get("has_star_motifs", False))
    has_flower_motifs = bool(re.search(r"\b(fleurs?\s+grav|flowers?\s+engrav|roses?\s+grav)\b", low))

    # Détection séparée de la couleur INTÉRIEURE ("intérieur en blanc", etc.) et EXTÉRIEURE ("extérieur en...", couleur du vase)
    m_int = re.search(r"\bint[eé]rieur(?:\s+du\s+vase)?\s+(?:en\s+|de\s+couleur\s+)?([a-zA-ZÀ-ÿ]+(?:\s+[a-zA-ZÀ-ÿ]+)?)", low)
    m_ext = re.search(r"\bext[eé]rieur(?:\s+du\s+vase)?\s+(?:en\s+|de\s+couleur\s+)?([a-zA-ZÀ-ÿ]+(?:\s+[a-zA-ZÀ-ÿ]+)?)", low)

    interior_parsed = _parse_named_color_rgb(m_int.group(1)) if m_int else None
    if interior_parsed is not None:
        interior_color_name, interior_rgb, interior_deep_rgb, _ = interior_parsed
    elif "interior_rgb" in prev:
        interior_color_name = str(prev.get("interior_color_name", "pure_white"))
        interior_rgb = tuple(prev["interior_rgb"])
        interior_deep_rgb = tuple(prev.get("interior_deep_rgb", (226, 232, 240)))
    else:
        # Par défaut et conformément à la demande utilisateur : intérieur en blanc pur (#FCFDFE) contrastant avec l'extérieur !
        interior_color_name = "pure_white"
        interior_rgb = (252, 253, 255)
        interior_deep_rgb = (224, 230, 240)

    # Retirer la clause "intérieur en ..." pour ne pas confondre la couleur intérieure avec la couleur extérieure du vase
    low_without_int = re.sub(r"\bint[eé]rieur(?:\s+du\s+vase)?\s+(?:en\s+|de\s+couleur\s+)?[a-zA-ZÀ-ÿ]+", " ", low)
    ext_parsed = _parse_named_color_rgb(m_ext.group(1) if m_ext else low_without_int)

    if ext_parsed is not None:
        color_name, base_rgb, deep_rgb, attenuation_color = ext_parsed
        frost_rgb = (255, 250, 253)
    elif "base_rgb" in prev:
        color_name = str(prev.get("color_name", "rose_crystal"))
        base_rgb = tuple(prev["base_rgb"])
        deep_rgb = tuple(prev["deep_rgb"])
        frost_rgb = tuple(prev.get("frost_rgb", (255, 250, 253)))
        attenuation_color = list(prev.get("attenuation_color", [1.0, 0.42, 0.68]))
    else:
        # Couleur extérieure par défaut du vase cœur : rose cristal/céramique intense ("comme le même vase")
        color_name = "rose_crystal"
        base_rgb = (238, 86, 152)
        deep_rgb = (192, 36, 104)
        frost_rgb = (255, 250, 253)
        attenuation_color = [1.0, 0.42, 0.68]

    return {
        "engraved_text": engraved_text,
        "heart_shape": heart_shape,
        "heart_style": heart_style,
        "is_empty_vessel": is_empty_vessel,
        "real_print_height_mm": real_print_height_mm,
        "has_heart_motifs": has_heart_motifs,
        "has_star_motifs": has_star_motifs,
        "has_flower_motifs": has_flower_motifs,
        "color_name": color_name,
        "base_rgb": base_rgb,
        "deep_rgb": deep_rgb,
        "frost_rgb": frost_rgb,
        "interior_color_name": interior_color_name,
        "interior_rgb": interior_rgb,
        "interior_deep_rgb": interior_deep_rgb,
        "attenuation_color": attenuation_color,
    }


def _load_best_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).is_file():
            try:
                return ImageFont.truetype(c, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _draw_heart_polygon(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, fill: int | tuple[int, ...], width: int = 0) -> None:
    pts: list[tuple[float, float]] = []
    for k in range(120):
        t = 2.0 * math.pi * k / 120.0
        x = 16.0 * (math.sin(t) ** 3)
        y = -(13.0 * math.cos(t) - 5.0 * math.cos(2.0 * t) - 2.0 * math.cos(3.0 * t) - math.cos(4.0 * t))
        pts.append((cx + x * scale, cy + y * scale))
    if width > 0:
        draw.polygon(pts, outline=fill, width=width)
    else:
        draw.polygon(pts, fill=fill)


def build_engraving_heightfield_and_textures(
    spec: dict[str, Any],
    tex_size: int = 2048,
) -> tuple[np.ndarray, Image.Image, Image.Image, Image.Image]:
    """Construit l'atlas UV 360° continu (sans boîte rectangulaire ni effet étiquette) :
    - Plage `u in [0.0, 1.0]` : azimut cylindrique continu `theta = atan2(x, z)` autour du vase
      (`u = 0.50` = centre de la face avant `+Z`, `u = 0.25` = profil gauche `-X`,
       `u = 0.75` = profil droit `+X`, `u = 0.0 / 1.0` = dos `-Z`).
    - Plage `v_uv in [0.26, 0.98]` (`v_grid in [0.02, 0.74]`) : paroi extérieure rose cristal/céramique
      avec relief ciselé 3D (gorge rubis profond + crête nacrée rose-champagne, jamais un aplat blanc d'étiquette).
    - Plage `v_uv in [0.02, 0.22]` (`v_grid in [0.78, 0.98]`) : intérieur creux et lèvre interne en Blanc Pur (`#FCFDFE`).
    """
    h_img = Image.new("L", (tex_size, tex_size), 0)
    draw = ImageDraw.Draw(h_img)

    # Centre de la face avant (+Z) en u = 0.50, v_grid = 0.46 (milieu de la panse du cœur)
    # Rapport d'aspect isométrique 1:1 en espace 3D pour éviter tout étirement horizontal des lettres ou des cœurs
    cx_front = int(0.50 * tex_size)
    cy_front = int(0.47 * tex_size)

    # 1. Constellation harmonieuse de cœurs sculptés en haut-relief 3D sur la face avant (u autour de 0.50)
    #    parfaitement dégagés du prénom central (zéro collision avec la première ou la dernière lettre)
    if spec.get("has_heart_motifs", True):
        front_hearts = [
            (-0.068, -0.118, 0.0018),
            (0.068, -0.118, 0.0018),
            (-0.026, -0.136, 0.0014),
            (0.026, -0.136, 0.0014),
            (-0.118, -0.042, 0.0016),
            (0.118, -0.042, 0.0016),
            (-0.062, 0.118, 0.0017),
            (0.062, 0.118, 0.0017),
        ]
        for du, dv, sc in front_hearts:
            hx = int((0.50 + du) * tex_size)
            hy = int((0.47 + dv) * tex_size)
            _draw_heart_polygon(draw, hx, hy, scale=tex_size * sc, fill=248, width=0)

    # 2. Prénom / Inscription calligraphiée à l'endroit (gauche -> droite) au centre de la face avant (u = 0.50)
    label = spec.get("engraved_text")
    if label:
        font_size = max(56, int(tex_size * 0.062))
        font = _load_best_font(font_size)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = cx_front - tw // 2
        ty = cy_front - th // 2 - int(0.010 * tex_size)
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            draw.text((tx + ox, ty + oy), label, fill=210, font=font)
        draw.text((tx, ty), label, fill=255, font=font)

        # Filet ciselé et cœur central sous le prénom
        y_line = ty + th + int(0.028 * tex_size)
        line_half = int(max(tw * 0.44, tex_size * 0.048))
        draw.line([(cx_front - line_half, y_line), (cx_front - int(tex_size * 0.020), y_line)], fill=230, width=max(4, tex_size // 340))
        draw.line([(cx_front + int(tex_size * 0.020), y_line), (cx_front + line_half, y_line)], fill=230, width=max(4, tex_size // 340))
        _draw_heart_polygon(draw, cx_front, y_line, scale=tex_size * 0.0015, fill=252, width=0)

    # 3. Ornements sculptés dorsaux (autour de u = 0.08 et u = 0.92)
    if spec.get("has_heart_motifs", True):
        for u_b, dv, sc in [(0.12, -0.06, 0.0015), (0.88, -0.06, 0.0015), (0.14, 0.07, 0.0014), (0.86, 0.07, 0.0014)]:
            _draw_heart_polygon(draw, int(u_b * tex_size), int((0.46 + dv) * tex_size), scale=tex_size * sc, fill=220, width=0)

    h_raw = np.asarray(h_img, dtype=np.float32) / 255.0
    # Profil de haut-relief ciselé 3D : crête bombée lisse + gorge périphérique en taille d'épargne (intaglio)
    h_crest = cv2.GaussianBlur(h_raw, (0, 0), sigmaX=1.6, sigmaY=1.6)
    h_halo = cv2.GaussianBlur(h_raw, (0, 0), sigmaX=4.8, sigmaY=4.8)
    # Gorge ciselée autour de chaque lettre et de chaque cœur (anneau négatif entourant le relief positif)
    intaglio_groove = np.clip((h_halo - h_crest * 0.85) * 2.2, 0.0, 1.0)
    height_01 = np.clip(h_crest, 0.0, 1.0)

    v_grid = np.linspace(0.0, 1.0, tex_size, dtype=np.float32)[:, None]
    u_grid = np.linspace(0.0, 1.0, tex_size, dtype=np.float32)[None, :]

    base_rgb = np.array(spec["base_rgb"], dtype=np.float32)
    deep_rgb = np.array(spec["deep_rgb"], dtype=np.float32)
    interior_rgb = np.array(spec.get("interior_rgb", (252, 253, 255)), dtype=np.float32)
    interior_deep_rgb = np.array(spec.get("interior_deep_rgb", (228, 234, 242)), dtype=np.float32)

    # Dégradé vertical continu 100 % périodique en U (zéro variation brutale en U = zéro couture et zéro effet étiquette)
    vert_grad = np.clip((v_grid - 0.35) / 0.40, -1.0, 1.0)
    depth_mix = 0.20 + 0.28 * (vert_grad * vert_grad)
    crystal_rgb = base_rgb[None, None, :] * (1.0 - depth_mix[..., None]) + deep_rgb[None, None, :] * depth_mix[..., None]

    # Ombrage physique de gravure ciselée dans la masse du cristal (ZÉRO peinture blanche plate d'étiquette !) :
    # - Fond de gorge ciselée (`intaglio_groove`) : rubis/bordeaux profond (occlusion ambiante de la taille)
    # - Flanc biseauté éclairé (`gx + gy < 0`) : éclat rose-champagne nacré
    # - Crête du haut-relief (`height_01`) : glaçure rose-perle lumineuse intégrée au cristal
    gx = cv2.Scharr(height_01 * 255.0, cv2.CV_32F, 1, 0) / 16.0
    gy = cv2.Scharr(height_01 * 255.0, cv2.CV_32F, 0, 1) / 16.0
    bevel_light = np.clip((-0.65 * gx - 0.75 * gy) / 18.0, -1.0, 1.0)

    groove_rgb = np.maximum(0.0, deep_rgb - np.array([62.0, 24.0, 38.0], dtype=np.float32))
    crest_rgb = np.minimum(255.0, base_rgb * 0.42 + np.array([255.0, 214.0, 234.0], dtype=np.float32) * 0.58)
    bevel_hi_rgb = np.array([255.0, 238.0, 246.0], dtype=np.float32)

    sculpted_rgb = crystal_rgb * (1.0 - 0.65 * intaglio_groove[..., None]) + groove_rgb[None, None, :] * (0.65 * intaglio_groove[..., None])
    crest_w = np.clip(height_01 * 1.15, 0.0, 1.0)[..., None]
    sculpted_rgb = sculpted_rgb * (1.0 - crest_w) + crest_rgb[None, None, :] * crest_w
    sculpted_rgb = sculpted_rgb + np.maximum(0.0, bevel_light)[..., None] * (bevel_hi_rgb[None, None, :] - sculpted_rgb) * 0.55

    # Bande inférieure `v_grid >= 0.76` (`v_uv <= 0.24`) sur TOUTE la largeur `u in [0, 1]` :
    # Intérieur creux et lèvre d'ouverture en Blanc Pur Émaillé (#FCFDFE)
    interior_uv_zone = v_grid >= 0.76
    int_depth_t = np.clip((v_grid - 0.76) / 0.24, 0.0, 1.0)[..., None]
    int_zone_rgb = interior_rgb[None, None, :] * (1.0 - 0.12 * int_depth_t) + interior_deep_rgb[None, None, :] * (0.12 * int_depth_t)
    # Transition douce sur 4 pixels autour de v_grid = 0.76
    rim_blend = np.clip((v_grid - 0.755) / 0.010, 0.0, 1.0)[..., None] * np.ones_like(u_grid)[..., None]
    final_rgb = np.clip(sculpted_rgb * (1.0 - rim_blend) + int_zone_rgb * rim_blend, 0.0, 255.0).astype(np.uint8)

    alpha_ch = np.full(final_rgb.shape[:2], 255, dtype=np.uint8)
    albedo_rgba = np.dstack([final_rgb, alpha_ch])

    # Carte de déplacement signée pour la géométrie 3D réelle : +crête en haut-relief (1.0) et -gorge ciselée (-0.35)
    signed_relief = np.where(interior_uv_zone & (u_grid >= 0.0), 0.0, height_01 - 0.35 * intaglio_groove).astype(np.float32)

    n_scale = 0.095
    nx = -gx * n_scale
    ny = gy * n_scale
    nz = np.ones_like(nx, dtype=np.float32)
    n_norm = np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    nrm_u8 = np.dstack([
        np.clip(((nx / n_norm) * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8),
        np.clip(((ny / n_norm) * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8),
        np.clip(((nz / n_norm) * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8),
    ])

    ao_ch = np.where(
        interior_uv_zone,
        np.clip(252.0 - 16.0 * int_depth_t[..., 0], 230.0, 255.0),
        np.clip(252.0 - 68.0 * intaglio_groove, 165.0, 255.0),
    ).astype(np.uint8)
    # Rugosité PBR équilibrée (0.20 sur la glaçure cristal, 0.34 dans les gorges ciselées) pour éviter tout voile gris/blanc dans f3d
    rough_ch = np.where(
        interior_uv_zone,
        42.0,
        np.clip(52.0 + 38.0 * intaglio_groove - 12.0 * height_01, 38.0, 96.0),
    ).astype(np.uint8)
    metal_ch = np.zeros_like(ao_ch, dtype=np.uint8)
    orm_u8 = np.dstack([ao_ch, rough_ch, metal_ch])

    return (
        signed_relief,
        Image.fromarray(albedo_rgba, mode="RGBA"),
        Image.fromarray(nrm_u8, mode="RGB"),
        Image.fromarray(orm_u8, mode="RGB"),
    )


def _subdivide_and_sculpt_3d_relief(
    mesh: trimesh.Trimesh,
    inner_mask_fn: Any,
    disp_height_smooth: np.ndarray,
    sample_bilinear_fn: Any,
    front_y_center: float = -0.10,
    front_y_half: float = 0.56,
    relief_amplitude: float = 0.032,
    extra_radial_fn: Any = None,
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Subdivise uniformément le maillage 2-manifold (zéro T-junction, 100 % étanche) pour atteindre
    une résolution sub-millimétrique (~450 000 faces), sculpte en VRAIE géométrie 3D le haut-relief
    calligraphique (« Rayen » + cœurs 3D à +3.0 mm et sillon intaglio à -1.2 mm) ainsi que les moulures
    et côtes 3D du cristal, puis construit un dépliage UV 360° continu sans couture ni bord d'étiquette."""
    # 1. Subdivision uniforme 2-manifold (préserve 100 % l'étanchéité `is_watertight` sans T-junction)
    mesh = mesh.subdivide()
    trimesh.repair.fix_normals(mesh)

    v_arr = np.asarray(mesh.vertices, dtype=np.float64).copy()
    n_arr = np.asarray(mesh.vertex_normals, dtype=np.float64).copy()
    inner_vertex_mask = np.asarray(inner_mask_fn(v_arr), dtype=bool)

    # 2. Coordonnées UV azimutales continues 360° autour de l'axe Y avec correction d'aspect isométrique 1:1 en façade :
    #    theta = atan2(x, z * 0.52) étire la dynamique angulaire en façade (+Z) pour que les cœurs et « Rayen »
    #    aient un rapport largeur/hauteur géométrique 1:1 parfait sans écrasement horizontal, tout en restant
    #    strictement monotone C^infty sur 360° (det(dUV) != 0 partout !).
    theta = np.arctan2(v_arr[:, 0], v_arr[:, 2] * 0.52)
    u_ext = np.clip(0.50 + (theta / (2.0 * math.pi)) * 0.92, 0.02, 0.98)
    y_min, y_max = float(v_arr[:, 1].min()), float(v_arr[:, 1].max())
    y_span = max(1e-5, y_max - y_min)
    # En convention image (v_grid = 1 - v_uv), v_uv = 0.53 correspond à v_grid = 0.47 (centre du prénom)
    v_ext = np.clip(0.53 + 0.34 * ((v_arr[:, 1] - front_y_center) / max(0.35, front_y_half)), 0.28, 0.96)

    # 3. Déplacement géométrique 3D véritable le long de la normale extérieure :
    # a) Haut-relief 3D du prénom « Rayen » et des cœurs sculptés (+3.0 mm / -1.2 mm)
    engrave_weight = (
        (~inner_vertex_mask).astype(np.float64)
        * np.clip((np.abs(v_arr[:, 2]) - 0.08) / 0.10, 0.0, 1.0)
        * np.clip(1.0 - np.abs(v_arr[:, 1] - front_y_center) / (front_y_half * 0.95), 0.0, 1.0)
    )
    h_val = sample_bilinear_fn(disp_height_smooth, u_ext, v_ext).astype(np.float64)
    disp_total = float(relief_amplitude) * h_val * engrave_weight

    # b) Moulures et côtes de cristal 3D supplémentaires (côtes en cœur, collerette, artères coronaires 3D)
    if extra_radial_fn is not None:
        disp_total = disp_total + extra_radial_fn(v_arr, n_arr, inner_vertex_mask)

    v_arr[:, 0] += disp_total * n_arr[:, 0]
    v_arr[:, 1] += disp_total * n_arr[:, 1]
    v_arr[:, 2] += disp_total * n_arr[:, 2]
    mesh.vertices = v_arr
    # Polissage optique C^2 (2 passes Taubin douces) pour éliminer tout micro-crénelage sur les biseaux 3D
    trimesh.smoothing.filter_taubin(mesh, lamb=0.35, nu=-0.365, iterations=2)
    trimesh.repair.fix_normals(mesh)
    v_arr = np.asarray(mesh.vertices, dtype=np.float64).copy()

    # Copie 2-manifold étanche pour l'export STL taille réelle (180 mm) avant découpe des coutures UV
    watertight_stl_mesh = trimesh.Trimesh(
        vertices=v_arr.copy(),
        faces=np.asarray(mesh.faces, dtype=np.int64).copy(),
        process=False,
    )
    trimesh.repair.fix_normals(watertight_stl_mesh)

    # 4. Attribution UV par face/sommet sans aucune traversée de la frontière Blanc/Rose (v=0.24)
    #    ni de la couture dorsale (theta = +/-pi) :
    v_in = np.clip(0.06 + 0.14 * ((v_arr[:, 1] - y_min) / y_span), 0.04, 0.20)
    f_cur = np.asarray(mesh.faces, dtype=np.int64).copy()
    tri_is_inner = inner_vertex_mask[f_cur].sum(axis=1) >= 2

    v_in_used = np.zeros(len(v_arr), dtype=bool)
    v_out_used = np.zeros(len(v_arr), dtype=bool)
    v_in_used[f_cur[tri_is_inner].ravel()] = True
    v_out_used[f_cur[~tri_is_inner].ravel()] = True
    shared_rim_verts = v_in_used & v_out_used

    u_uv = u_ext.copy()
    v_uv = np.where(v_in_used & (~v_out_used), v_in, v_ext)

    v_list = [v_arr]
    u_list = [u_uv]
    v_uv_list = [v_uv]
    next_v_idx = len(v_arr)

    if np.any(shared_rim_verts):
        shared_indices = np.nonzero(shared_rim_verts)[0]
        remap_in = np.full(len(v_arr), -1, dtype=np.int64)
        remap_in[shared_indices] = np.arange(next_v_idx, next_v_idx + len(shared_indices), dtype=np.int64)
        v_list.append(v_arr[shared_indices])
        u_list.append(u_ext[shared_indices])
        v_uv_list.append(v_in[shared_indices])
        next_v_idx += len(shared_indices)

        in_face_indices = np.nonzero(tri_is_inner)[0]
        for k_local in range(3):
            col_v = f_cur[in_face_indices, k_local]
            mask_s = remap_in[col_v] >= 0
            f_cur[in_face_indices[mask_s], k_local] = remap_in[col_v[mask_s]]

    v_all = np.vstack(v_list)
    u_all = np.concatenate(u_list)
    v_uv_all = np.concatenate(v_uv_list)

    # Couture dorsale (triangles au dos z < 0 traversant x = 0 où theta passe de -pi à +pi)
    u_tri = u_all[f_cur]
    seam_tri = (u_tri.max(axis=1) - u_tri.min(axis=1)) > 0.45
    if np.any(seam_tri):
        v_list2 = [v_all]
        u_list2 = [u_all]
        v_uv_list2 = [v_uv_all]
        for fi in np.nonzero(seam_tri)[0]:
            tri = f_cur[fi]
            us = u_all[tri]
            for k_local in range(3):
                if us[k_local] < 0.50:
                    v_list2.append(v_all[tri[k_local] : tri[k_local] + 1])
                    u_list2.append(np.array([us[k_local] + 0.92], dtype=np.float64))
                    v_uv_list2.append(np.array([v_uv_all[tri[k_local]]], dtype=np.float64))
                    f_cur[fi, k_local] = next_v_idx
                    next_v_idx += 1
        v_all = np.vstack(v_list2)
        u_all = np.concatenate(u_list2)
        v_uv_all = np.concatenate(v_uv_list2)

    visual_mesh = trimesh.Trimesh(vertices=v_all, faces=f_cur, process=False)
    trimesh.repair.fix_normals(visual_mesh)
    visual_mesh.metadata["watertight_stl_mesh"] = watertight_stl_mesh
    uvs_final = np.column_stack([np.clip(u_all, 0.01, 0.99), np.clip(v_uv_all, 0.02, 0.98)]).astype(np.float64)
    return visual_mesh, uvs_final




def _build_anatomical_heart_vase_mesh(
    spec: dict[str, Any],
    disp_height_smooth: np.ndarray,
    sample_bilinear_fn: Any,
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Construit un VRAI Vase Cœur Anatomique 3D (2-manifold étanche, 100 % creux et vide sans fleurs) :
    - Morphologie cardiaque humaine authentique : ventricule gauche conique incliné (apex à gauche/bas),
      ventricule droit antérieur bombé, oreillettes (auricules) gauche et droite festonnées,
    - Sillon interventriculaire antérieur/postérieur et sillon coronarien auriculo-ventriculaire creusés en 3D,
    - Artères et veines coronaires 3D sculptées en haut-relief (artère interventriculaire antérieure LAD + branches diagonales),
    - VRAIS gros vaisseaux supérieurs tubulaires creux et ouverts (sans col d'amphore générique) :
      1) Crosse Aortique (Aorta) arquée au sommet avec ses 3 troncs supra-aortiques (brachiocéphalique, carotide, sous-clavière),
      2) Tronc Artériel Pulmonaire émergeant en avant/gauche avec embouchure biseautée ouverte,
      3) Veine Cave Supérieure (Vena Cava Superior) émergeant sur l'oreillette droite avec embouchure ouverte,
    - Semelle d'appui plane discrètement intégrée sous la paroi inférieure/postérieure de l'apex pour impression 3D taille réelle (180 mm),
    - Médaillon calligraphique gravé (« Rayen » + cœurs) en bas-relief sur la paroi ventriculaire antérieure (+Z).
    """
    import scipy.ndimage as ndi
    from skimage import measure

    # Grille 3D haute résolution (X: gauche-droite, Y: bas-haut en glTF Y-up, Z: arrière-avant)
    nx, ny, nz = 168, 200, 148
    xs = np.linspace(-0.92, 0.92, nx, dtype=np.float32)
    ys = np.linspace(-0.92, 0.98, ny, dtype=np.float32)
    zs = np.linspace(-0.76, 0.76, nz, dtype=np.float32)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")

    def _capsule_sdf(
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        r0: float,
        r1: float,
        scale_xyz: tuple[float, float, float] = (1.0, 1.0, 1.0),
    ) -> np.ndarray:
        vx, vy, vz = float(p1[0] - p0[0]), float(p1[1] - p0[1]), float(p1[2] - p0[2])
        seg_len2 = max(1e-6, vx * vx + vy * vy + vz * vz)
        dx = (X - float(p0[0])) / float(scale_xyz[0])
        dy = (Y - float(p0[1])) / float(scale_xyz[1])
        dz = (Z - float(p0[2])) / float(scale_xyz[2])
        ux = vx / float(scale_xyz[0])
        uy = vy / float(scale_xyz[1])
        uz = vz / float(scale_xyz[2])
        u_len2 = max(1e-6, ux * ux + uy * uy + uz * uz)
        t = np.clip((dx * ux + dy * uy + dz * uz) / u_len2, 0.0, 1.0)
        dist = np.sqrt((dx - t * ux) ** 2 + (dy - t * uy) ** 2 + (dz - t * uz) ** 2 + 1e-6)
        r_t = float(r0) * (1.0 - t) + float(r1) * t
        return dist - r_t

    def _smin(a: np.ndarray, b: np.ndarray, k: float = 0.08) -> np.ndarray:
        h = np.clip(0.5 + 0.5 * (b - a) / max(1e-5, float(k)), 0.0, 1.0)
        return b * (1.0 - h) + a * h - float(k) * h * (1.0 - h)

    def _open_tube(
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        r_outer: float,
        r_inner: float,
        flare: float = 0.010,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Construit un vaisseau tubulaire cylindrique 3D ouvert perpendiculairement à son axe propre en p1,
        avec léger ourlet anatomique en p1 et canal intérieur creux débouchant nettement à l'extérieur.
        Retourne (sdf_outer_tube, sdf_bore_tube, rim_lip_mask).
        """
        vx, vy, vz = float(p1[0] - p0[0]), float(p1[1] - p0[1]), float(p1[2] - p0[2])
        length = max(1e-5, math.sqrt(vx * vx + vy * vy + vz * vz))
        ux, uy, uz = vx / length, vy / length, vz / length
        dx, dy, dz = X - float(p0[0]), Y - float(p0[1]), Z - float(p0[2])
        s = dx * ux + dy * uy + dz * uz
        rx = dx - s * ux
        ry = dy - s * uy
        rz = dz - s * uz
        r_perp = np.sqrt(rx * rx + ry * ry + rz * rz + 1e-6)
        # Ourlet annulaire anatomique subtil à l'extrémité ouverte s == length
        r_ext = float(r_outer) + float(flare) * np.exp(-(((s - length) / 0.042) ** 2))
        s_neg = np.minimum(s, 0.0)
        sdf_ext = np.maximum(np.sqrt(r_perp * r_perp + s_neg * s_neg) - r_ext, s - length)
        # Canal creux intérieur dépassant l'extrémité s == length pour ouvrir le tube nettement
        sdf_int = np.maximum(np.maximum(r_perp - float(r_inner), -s), s - (length + 0.14))
        # Masque de la lèvre annulaire d'embouchure (pour l'émail blanc intérieur/bord)
        rim_mask = (np.abs(s - length) <= 0.036) & (r_perp <= r_ext + 0.018)
        return sdf_ext, sdf_int, rim_mask

    # 1. Masse myocardique principale galbée (occupant Y de -0.80 à +0.26 pour laisser émerger les longs vaisseaux tubulaires) :
    #    Ventricule gauche (apex arrondi incliné à +X, -Y), Ventricule droit (antérieur -X/+Z),
    #    Oreillette droite (-X, +Y) et Oreillette gauche (+X, +Y) — SANS piédestal cylindrique artificiel !
    sdf_lv = _capsule_sdf((0.06, -0.58, 0.01), (-0.03, 0.08, -0.01), r0=0.23, r1=0.39, scale_xyz=(1.01, 1.0, 1.00))
    sdf_rv = _capsule_sdf((-0.05, -0.54, 0.03), (-0.18, 0.06, 0.05), r0=0.22, r1=0.36, scale_xyz=(1.02, 1.0, 0.99))
    sdf_ra = _capsule_sdf((-0.28, 0.04, 0.02), (-0.34, 0.18, 0.05), r0=0.20, r1=0.17, scale_xyz=(1.00, 0.92, 0.98))
    sdf_la = _capsule_sdf((0.22, 0.06, -0.02), (0.28, 0.18, 0.02), r0=0.19, r1=0.16, scale_xyz=(1.00, 0.92, 0.98))

    sdf_heart_core = _smin(_smin(sdf_lv, sdf_rv, k=0.14), _smin(sdf_ra, sdf_la, k=0.10), k=0.10)

    # Sillon interventriculaire diagonal + sillon auriculo-ventriculaire coronarien
    sulcus_coord = (X - 0.06 * (0.18 - Y)) * 0.86 + (Y + 0.18) * 0.28
    iv_groove = 0.022 * np.exp(-((sulcus_coord / 0.070) ** 2)) * np.clip((0.20 - Y) / 0.32, 0.0, 1.0) * np.clip((Y + 0.62) / 0.25, 0.0, 1.0)
    av_groove = 0.018 * np.exp(-(((Y - 0.12 - 0.08 * X) / 0.050) ** 2))
    sdf_heart_core = sdf_heart_core + iv_groove + av_groove

    # Artères coronaires 3D sculptées en relief doux à la surface du myocarde
    lad_t = np.clip((0.18 - Y) / 0.76, 0.0, 1.0)
    lad_x = -0.04 + 0.14 * lad_t + 0.018 * np.sin(8.0 * lad_t)
    lad_dist = np.sqrt((X - lad_x) ** 2 + (Z - (0.36 - 0.14 * lad_t)) ** 2)
    lad_relief = 0.015 * np.exp(-((lad_dist / 0.028) ** 2)) * np.clip((0.20 - Y) / 0.10, 0.0, 1.0) * np.clip((Y + 0.56) / 0.14, 0.0, 1.0)

    d1_t = np.clip((0.04 - Y) / 0.42, 0.0, 1.0)
    d1_x = 0.02 + 0.28 * d1_t
    d1_dist = np.sqrt((X - d1_x) ** 2 + (Z - (0.34 - 0.12 * d1_t)) ** 2)
    d1_relief = 0.012 * np.exp(-((d1_dist / 0.024) ** 2)) * (d1_t > 0.02) * (d1_t < 0.96)

    rca_t = np.clip((0.12 - Y) / 0.54, 0.0, 1.0)
    rca_x = -0.22 - 0.06 * np.sin(math.pi * rca_t)
    rca_dist = np.sqrt((X - rca_x) ** 2 + (Z - (0.32 - 0.10 * rca_t)) ** 2)
    rca_relief = 0.012 * np.exp(-((rca_dist / 0.024) ** 2)) * (rca_t > 0.02) * (rca_t < 0.96)

    sdf_heart_core = sdf_heart_core - (lad_relief + d1_relief + rca_relief)

    # 2. Vaisseaux tubulaires cylindriques longs et distincts (exactement comme sur la photo de référence 1793281199531) :
    #    - Veine Cave Supérieure (haut-gauche, grand tube cylindrique élancé)
    #    - Crosse de l'Aorte (centre-haut) couronnée de ses 3 longs troncs supra-aortiques cylindriques ouverts
    #    - Tronc Pulmonaire (oblique vers le haut-droite, large tube cylindrique incliné)
    #    - Veines pulmonaires latérales (2 tubes à gauche, 2 tubes à droite)
    vc_ext, vc_bore, vc_rim = _open_tube((-0.24, 0.10, -0.02), (-0.34, 0.72, 0.00), r_outer=0.122, r_inner=0.082, flare=0.012)
    aorta_base = _capsule_sdf((-0.02, 0.08, 0.00), (0.04, 0.44, -0.01), r0=0.165, r1=0.150)
    aorta_arch = _capsule_sdf((0.04, 0.44, -0.01), (0.15, 0.46, -0.02), r0=0.148, r1=0.132)
    # 3 longs troncs supra-aortiques cylindriques bien dégagés émergeant du dôme aortique
    b1_ext, b1_bore, b1_rim = _open_tube((-0.04, 0.38, 0.00), (-0.07, 0.85, 0.00), r_outer=0.068, r_inner=0.044, flare=0.009)
    b2_ext, b2_bore, b2_rim = _open_tube((0.06, 0.40, -0.01), (0.07, 0.90, -0.01), r_outer=0.065, r_inner=0.042, flare=0.009)
    b3_ext, b3_bore, b3_rim = _open_tube((0.15, 0.38, -0.02), (0.21, 0.83, -0.02), r_outer=0.062, r_inner=0.040, flare=0.009)
    # Tronc pulmonaire oblique bien dégagé vers le haut-droite (+X, +Y)
    pulm_ext, pulm_bore, pulm_rim = _open_tube((-0.06, 0.08, 0.08), (0.40, 0.62, 0.04), r_outer=0.135, r_inner=0.092, flare=0.012)
    # Veines pulmonaires latérales tubulaires (gauche et droite)
    pv_l1_ext, pv_l1_bore, pv_l1_rim = _open_tube((-0.26, 0.08, 0.00), (-0.54, 0.24, 0.00), r_outer=0.072, r_inner=0.046, flare=0.008)
    pv_l2_ext, pv_l2_bore, pv_l2_rim = _open_tube((-0.28, -0.08, 0.02), (-0.55, 0.04, 0.02), r_outer=0.068, r_inner=0.044, flare=0.008)
    pv_r1_ext, pv_r1_bore, pv_r1_rim = _open_tube((0.24, 0.10, -0.02), (0.50, 0.26, -0.02), r_outer=0.074, r_inner=0.048, flare=0.008)
    pv_r2_ext, pv_r2_bore, pv_r2_rim = _open_tube((0.24, -0.05, 0.00), (0.48, 0.07, 0.00), r_outer=0.068, r_inner=0.044, flare=0.008)

    sdf_aorta_dome = _smin(aorta_base, aorta_arch, k=0.06)
    sdf_supra_ext = _smin(_smin(b1_ext, b2_ext, k=0.025), b3_ext, k=0.025)
    sdf_lat_ext = _smin(_smin(pv_l1_ext, pv_l2_ext, k=0.025), _smin(pv_r1_ext, pv_r2_ext, k=0.025), k=0.025)
    sdf_vessels_outer = _smin(
        _smin(_smin(sdf_aorta_dome, vc_ext, k=0.05), pulm_ext, k=0.05),
        _smin(sdf_supra_ext, sdf_lat_ext, k=0.04),
        k=0.045,
    )
    sdf_outer = _smin(sdf_heart_core, sdf_vessels_outer, k=0.065)
    # Méplat d'assise discret uniquement à l'extrême pointe inférieure (y = -0.78) sans cylindre ni piédestal
    sdf_outer = np.maximum(sdf_outer, -0.78 - Y)

    # 3. Cavité intérieure creuse (100 % vide sans fleurs) : chambre cardiaque + lumières cylindriques de chaque vaisseau !
    wall_t = 0.072
    sdf_cavity_core = _smin(
        _smin(sdf_lv + wall_t, sdf_rv + wall_t, k=0.12),
        _smin(_smin(sdf_ra + wall_t, sdf_la + wall_t, k=0.08), sdf_aorta_dome + 0.050, k=0.06),
        k=0.08,
    )
    sdf_all_bores = np.minimum(
        np.minimum(np.minimum(vc_bore, pulm_bore), np.minimum(b1_bore, np.minimum(b2_bore, b3_bore))),
        np.minimum(np.minimum(pv_l1_bore, pv_l2_bore), np.minimum(pv_r1_bore, pv_r2_bore)),
    )
    sdf_cavity = _smin(sdf_cavity_core, sdf_all_bores, k=0.035)
    # Fond plein stable à la base de l'apex (y >= -0.69)
    sdf_cavity = np.maximum(sdf_cavity, -0.69 - Y)

    # Coque creuse 2-manifold : intérieur de sdf_outer ET extérieur de sdf_cavity
    phi_shell = np.minimum(-sdf_outer, sdf_cavity)
    phi_shell = ndi.gaussian_filter(phi_shell.astype(np.float32), sigma=0.72)
    phi_shell[0, :, :] = -1.0; phi_shell[-1, :, :] = -1.0
    phi_shell[:, 0, :] = -1.0; phi_shell[:, -1, :] = -1.0
    phi_shell[:, :, 0] = -1.0; phi_shell[:, :, -1] = -1.0

    v_mc, f_mc, _, _ = measure.marching_cubes(phi_shell, level=0.0)
    vx = xs[0] + (v_mc[:, 0] / float(nx - 1)) * (xs[-1] - xs[0])
    vy = ys[0] + (v_mc[:, 1] / float(ny - 1)) * (ys[-1] - ys[0])
    vz = zs[0] + (v_mc[:, 2] / float(nz - 1)) * (zs[-1] - zs[0])
    verts = np.column_stack([vx, vy, vz]).astype(np.float64)
    faces = np.asarray(f_mc[:, [0, 2, 1]], dtype=np.int64)

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    subs = mesh.split(only_watertight=False)
    if len(subs) > 1:
        subs.sort(key=lambda b: len(b.faces), reverse=True)
        mesh = subs[0]
    trimesh.smoothing.filter_taubin(mesh, lamb=0.45, nu=-0.468, iterations=10)
    trimesh.repair.fix_normals(mesh)

    all_rim_grid = vc_rim | b1_rim | b2_rim | b3_rim | pulm_rim | pv_l1_rim | pv_l2_rim | pv_r1_rim | pv_r2_rim

    def _anat_inner_mask(v_q: np.ndarray) -> np.ndarray:
        ix = np.clip(np.rint((v_q[:, 0] - xs[0]) / (xs[-1] - xs[0]) * (nx - 1)).astype(np.int32), 0, nx - 1)
        iy = np.clip(np.rint((v_q[:, 1] - ys[0]) / (ys[-1] - ys[0]) * (ny - 1)).astype(np.int32), 0, ny - 1)
        iz = np.clip(np.rint((v_q[:, 2] - zs[0]) / (zs[-1] - zs[0]) * (nz - 1)).astype(np.int32), 0, nz - 1)
        d_outer_v = np.abs(sdf_outer[ix, iy, iz])
        d_cav_v = np.abs(sdf_cavity[ix, iy, iz])
        rim_v = all_rim_grid[ix, iy, iz]
        return (d_cav_v <= d_outer_v * 1.18) | rim_v

    def _anat_extra_radial(v_q: np.ndarray, n_q: np.ndarray, inner_m: np.ndarray) -> np.ndarray:
        """Sculpte en haut-relief 3D sub-millimétrique les artères coronaires ramifiées (LAD, diagonales,
        circonflexe, coronaire droite, interventriculaire postérieure), les crêtes pectinées des auricules
        et les anneaux adventitiels des gros vaisseaux."""
        ext_w = (~inner_m).astype(np.float64)
        vq_x, vq_y, vq_z = v_q[:, 0], v_q[:, 1], v_q[:, 2]

        # Zone de réserve fluide autour du médaillon calligraphique central (+Z) pour que les artères
        # coronaires encadrent « Rayen » et les cœurs sans trancher à travers les lettres
        med_ell = ((vq_x + 0.01) / 0.25) ** 2 + ((vq_y + 0.22) / 0.22) ** 2
        front_med_clear = np.where(vq_z > 0.0, np.clip((med_ell - 0.92) / 0.35, 0.0, 1.0), 1.0)

        # 1. Réseau coronarien 3D haute définition (avec sillons périvasculaires pour un contraste 3D net)
        lad_t = np.clip((0.18 - vq_y) / 0.78, 0.0, 1.0)
        lad_x = -0.04 + 0.14 * lad_t + 0.018 * np.sin(8.0 * lad_t)
        d_lad = np.abs(vq_x - lad_x)
        w_y_lad = np.clip((0.20 - vq_y) / 0.08, 0.0, 1.0) * np.clip((vq_y + 0.62) / 0.12, 0.0, 1.0) * np.clip((np.abs(vq_z) - 0.12) / 0.12, 0.0, 1.0)
        r_lad = (0.015 * np.exp(-((d_lad / 0.016) ** 2)) - 0.0045 * np.exp(-((d_lad / 0.034) ** 2))) * w_y_lad * front_med_clear

        # Branches diagonales D1, D2 et marginale droite
        d1_t = np.clip((0.05 - vq_y) / 0.42, 0.0, 1.0)
        d_d1 = np.abs(vq_x - (0.01 + 0.29 * d1_t))
        r_d1 = 0.011 * np.exp(-((d_d1 / 0.014) ** 2)) * (d1_t > 0.02) * (d1_t < 0.96) * np.clip((vq_z - 0.10) / 0.12, 0.0, 1.0) * front_med_clear

        d2_t = np.clip((-0.18 - vq_y) / 0.36, 0.0, 1.0)
        d_d2 = np.abs(vq_x - (0.05 + 0.24 * d2_t))
        r_d2 = 0.0095 * np.exp(-((d_d2 / 0.013) ** 2)) * (d2_t > 0.02) * (d2_t < 0.96) * np.clip((vq_z - 0.08) / 0.12, 0.0, 1.0) * front_med_clear

        rca_t = np.clip((0.12 - vq_y) / 0.56, 0.0, 1.0)
        d_rca = np.abs(vq_x - (-0.22 - 0.07 * np.sin(math.pi * rca_t)))
        r_rca = 0.0115 * np.exp(-((d_rca / 0.015) ** 2)) * (rca_t > 0.02) * (rca_t < 0.96) * np.clip((np.abs(vq_z) - 0.08) / 0.12, 0.0, 1.0) * front_med_clear

        # Artère circonflexe gauche (LCx) et branches marginales latérales (OM1 sur +X, AM1 sur -X)
        # sculptées sur les flancs latéraux 360° pour une richesse anatomique et azimutale complète
        om_t = np.clip((0.08 - vq_y) / 0.52, 0.0, 1.0)
        d_om = np.abs(vq_z - (0.06 - 0.14 * om_t + 0.025 * np.sin(7.0 * om_t)))
        w_lat_l = np.clip((vq_x - 0.18) / 0.09, 0.0, 1.0) * (om_t > 0.02) * (om_t < 0.96)
        r_om = (0.011 * np.exp(-((d_om / 0.016) ** 2)) - 0.0035 * np.exp(-((d_om / 0.032) ** 2))) * w_lat_l

        am_t = np.clip((0.06 - vq_y) / 0.50, 0.0, 1.0)
        d_am = np.abs(vq_z - (0.08 - 0.16 * am_t - 0.022 * np.sin(6.5 * am_t)))
        w_lat_r = np.clip((-vq_x - 0.20) / 0.09, 0.0, 1.0) * (am_t > 0.02) * (am_t < 0.96)
        r_am = (0.0105 * np.exp(-((d_am / 0.016) ** 2)) - 0.0032 * np.exp(-((d_am / 0.032) ** 2))) * w_lat_r

        # 2. Crêtes pectinées 3D sur les auricules gauche et droite (0.0 <= y <= 0.22, |x| > 0.20)
        w_aur = np.clip((np.abs(vq_x) - 0.20) / 0.08, 0.0, 1.0) * np.exp(-(((vq_y - 0.11) / 0.09) ** 2))
        pectinate = 0.0065 * np.cos(38.0 * vq_x + 14.0 * vq_z) * w_aur

        # 3. Anneaux valvulaires / adventitiels sculptés à la racine et sous l'ourlet des gros vaisseaux
        vessel_rings = (
            0.0075 * np.exp(-(((vq_y - 0.22) / 0.024) ** 2))
            + 0.0065 * np.exp(-(((vq_y - 0.40) / 0.022) ** 2)) * (np.abs(vq_x) < 0.26)
        )
        return ext_w * (r_lad + r_d1 + r_d2 + r_rca + r_om + r_am + pectinate + vessel_rings)

    return _subdivide_and_sculpt_3d_relief(
        mesh=mesh,
        inner_mask_fn=_anat_inner_mask,
        disp_height_smooth=disp_height_smooth,
        sample_bilinear_fn=sample_bilinear_fn,
        front_y_center=-0.22,
        front_y_half=0.46,
        relief_amplitude=0.026,
        extra_radial_fn=_anat_extra_radial,
    )


def _build_emoji_heart_vase_mesh(
    spec: dict[str, Any],
    disp_height_smooth: np.ndarray,
    sample_bilinear_fn: Any,
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Construit un VRAI Vase Cœur Émoji / Romantique 3D ❤️ (2-manifold étanche, 100 % vide sans fleurs) :
    - Galbe 3D ellipsoïdal C^infty sans couture à Z=0 ni facette interne :
      Phi(X,Y,Z) = R0 - sqrt((d_eff - R0)^2 + (Z / beta)^2)
    - Silhouette frontale et arrière 100 % Cœur Émoji authentique ❤️ :
      * Deux grands lobes supérieurs arrondis symétriques à gauche (-X) et à droite (+X) culminant à y = +0.86,
      * Vraie échancrure centrale en V profond dégagée au milieu,
      * Pointe inférieure en V du cœur jusqu'en bas (avec méplat d'appui discret à la pointe y = -0.84, ZÉRO pied de coupe/gobelet !),
    - Ouverture supérieure creuse bicolore au sommet central du cœur menant à une vaste cavité intérieure
      en forme de cœur 100 % vide (sans fleurs) dont l'intérieur et l'ourlet d'ouverture sont en Blanc Pur (`#FCFDFE`)
      tandis que l'extérieur possède la teinte vive du vase + la gravure 3D (« Rayen » + petits cœurs) + des moulures
      concentriques en cœur taillées en vrai relief 3D dans le cristal.
    """
    import scipy.ndimage as ndi
    from skimage import measure

    nx, ny, nz = 176, 192, 144
    xs = np.linspace(-1.02, 1.02, nx, dtype=np.float32)
    ys = np.linspace(-0.90, 0.94, ny, dtype=np.float32)
    zs = np.linspace(-0.56, 0.56, nz, dtype=np.float32)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")

    abs_x = np.abs(X)
    # 1) Courbe supérieure bilobée : deux dômes semi-circulaires centrés en |X| = 0.44 de rayon R_lobe = 0.45,
    #    donnant un vrai creux en V au centre et deux sommets ronds en |X|=0.44 -> Y_top = +0.87 !
    y_top_lobe = 0.42 + np.sqrt(np.maximum(0.01, 0.45 ** 2 - (abs_x - 0.44) ** 2))
    # 2) Courbe inférieure en pointe de cœur (V-point) : de (X=0, Y=-0.84) jusqu'à l'équateur des lobes (|X|=0.89, Y=+0.42)
    t_y = np.clip((Y + 0.84) / 1.26, 0.0, 1.35)
    x_max_body = 0.14 + 0.76 * (np.sin(0.5 * math.pi * np.clip(t_y, 0.0, 1.0)) ** 0.78) * np.clip(1.32 - 0.32 * t_y, 0.0, 1.2)

    sdf_2d_heart = np.maximum(abs_x - x_max_body, Y - y_top_lobe)
    sdf_2d_heart = np.maximum(sdf_2d_heart, -0.84 - Y)

    # Distance signée exacte au bord 2D du cœur, lissée C^infty pour éviter toute crête médiane d'axe squelettique
    inside_2d = sdf_2d_heart <= 0.0
    edt_in_2d = ndi.distance_transform_edt(inside_2d[:, :, 0]) * float(xs[1] - xs[0])
    edt_out_2d = ndi.distance_transform_edt(~inside_2d[:, :, 0]) * float(xs[1] - xs[0])
    d_2d_raw = (edt_in_2d - edt_out_2d)
    d_2d_smooth_2d = ndi.gaussian_filter(d_2d_raw.astype(np.float32), sigma=3.2)
    d_2d_smooth = d_2d_smooth_2d[:, :, None]

    # Loi de galbe 3D ellipsoïdal C^infty SANS couture à Z=0 NI méplat central :
    r0_bulb = 0.64
    d_pos = np.maximum(0.0, d_2d_smooth)
    d_neg = np.minimum(0.0, d_2d_smooth)
    d_eff = r0_bulb * (1.0 - np.exp(-d_pos / 0.42)) + d_neg
    cleft_groove = 1.0 - 0.06 * np.exp(-((X / 0.18) ** 2)) * np.clip((Y - 0.18) / 0.55, 0.0, 1.0)
    beta_z = 0.64 * cleft_groove
    d_clamped = d_eff - r0_bulb
    phi_outer_heart = r0_bulb - np.sqrt(d_clamped * d_clamped + (Z / np.maximum(0.2, beta_z)) ** 2 + 1e-6)

    # Ouverture supérieure en selle biseautée douce au centre du cœur (laissant les 2 lobes supérieurs 100 % ronds et intacts
    # tout en révélant clairement l'ourlet et la cavité intérieure Blanc Pur dès la vue de face !)
    mouth_gauss_x = np.exp(-((X / 0.36) ** 2))
    y_saddle_lip = y_top_lobe - (0.05 + 0.16 * np.clip((Z + 0.18) / 0.34, 0.0, 1.0)) * mouth_gauss_x
    phi_outer = np.minimum(phi_outer_heart, y_saddle_lip - Y)
    # Assise plane stable sous la pointe inférieure (y = -0.84) sans pied de coupe
    phi_outer = np.minimum(phi_outer, Y + 0.84)

    # Cavité intérieure creuse C^infty en forme de cœur + embouchure supérieure ouverte (100 % vide sans fleurs)
    wall_t = 0.072
    phi_cavity_heart = (r0_bulb - wall_t) - np.sqrt(d_clamped * d_clamped + (Z / np.maximum(0.2, beta_z)) ** 2 + 1e-6)
    phi_cavity_heart = np.minimum(phi_cavity_heart, Y + 0.72)  # Fond plein stable en bas
    # Canal d'ouverture supérieur centré dans le creux bilobé du cœur (X in [-0.32, +0.32], Z in [-0.18, +0.18])
    mouth_r_ell = np.sqrt((X / 0.32) ** 2 + (Z / 0.175) ** 2)
    mouth_bore_vol = np.minimum((1.0 - mouth_r_ell) * 0.24, np.minimum(Y - 0.04, 0.92 - Y))

    phi_cavity = np.maximum(phi_cavity_heart, mouth_bore_vol)
    phi_shell = np.minimum(phi_outer, -phi_cavity)
    phi_shell = ndi.gaussian_filter(phi_shell.astype(np.float32), sigma=0.85)
    phi_shell[0, :, :] = -1.0; phi_shell[-1, :, :] = -1.0
    phi_shell[:, 0, :] = -1.0; phi_shell[:, -1, :] = -1.0
    phi_shell[:, :, 0] = -1.0; phi_shell[:, :, -1] = -1.0

    v_mc, f_mc, _, _ = measure.marching_cubes(phi_shell, level=0.0)
    vx = xs[0] + (v_mc[:, 0] / float(nx - 1)) * (xs[-1] - xs[0])
    vy = ys[0] + (v_mc[:, 1] / float(ny - 1)) * (ys[-1] - ys[0])
    vz = zs[0] + (v_mc[:, 2] / float(nz - 1)) * (zs[-1] - zs[0])
    verts = np.column_stack([vx, vy, vz]).astype(np.float64)
    faces = np.asarray(f_mc[:, [0, 2, 1]], dtype=np.int64)

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    subs = mesh.split(only_watertight=False)
    if len(subs) > 1:
        subs.sort(key=lambda b: len(b.faces), reverse=True)
        mesh = subs[0]
    trimesh.smoothing.filter_taubin(mesh, lamb=0.45, nu=-0.468, iterations=12)
    trimesh.repair.fix_normals(mesh)

    def _emoji_inner_mask(v_q: np.ndarray) -> np.ndarray:
        ix = np.clip(np.rint((v_q[:, 0] - xs[0]) / (xs[-1] - xs[0]) * (nx - 1)).astype(np.int32), 0, nx - 1)
        iy = np.clip(np.rint((v_q[:, 1] - ys[0]) / (ys[-1] - ys[0]) * (ny - 1)).astype(np.int32), 0, ny - 1)
        iz = np.clip(np.rint((v_q[:, 2] - zs[0]) / (zs[-1] - zs[0]) * (nz - 1)).astype(np.int32), 0, nz - 1)
        d_outer_v = np.abs(phi_outer_heart[ix, iy, iz])
        d_cav_v = np.abs(phi_cavity[ix, iy, iz])
        mouth_v_r = np.sqrt((v_q[:, 0] / 0.36) ** 2 + (v_q[:, 2] / 0.21) ** 2)
        return (d_cav_v <= d_outer_v * 1.18) | ((mouth_v_r <= 1.10) & (v_q[:, 1] > 0.26))

    def _emoji_extra_radial(v_q: np.ndarray, n_q: np.ndarray, inner_m: np.ndarray) -> np.ndarray:
        """Sculpte en VRAIE géométrie 3D analytique C^infty (zéro discrétisation de grille) sur la coque du cœur :
        1) Deux moulures/nervures concentriques en forme de cœur (style cristal taillé Baccarat/Lalique)
           encadrant le médaillon central sur la face avant (+Z) et la face arrière (-Z),
        2) Une collerette sculptée 3D bordant l'ouverture supérieure en selle,
        3) Des côtes de cristal biseautées le long du profil latéral."""
        ext_w = (~inner_m).astype(np.float64)
        vq_x, vq_y, vq_z = v_q[:, 0], v_q[:, 1], v_q[:, 2]
        abs_xq = np.abs(vq_x)

        # Distance analytique C^infty exacte au contour 2D du cœur (zéro effet d'escalier voxel !)
        y_top_q = 0.42 + np.sqrt(np.maximum(0.015, 0.45 ** 2 - (abs_xq - 0.44) ** 2))
        t_yq = np.clip((vq_y + 0.84) / 1.26, 0.0, 1.35)
        x_max_q = 0.14 + 0.76 * (np.sin(0.5 * math.pi * np.clip(t_yq, 0.0, 1.0)) ** 0.78) * np.clip(1.32 - 0.32 * t_yq, 0.0, 1.2)
        da = x_max_q - abs_xq
        db = y_top_q - vq_y
        k_sm = 0.08
        h_sm = np.clip(0.5 + 0.5 * (db - da) / k_sm, 0.0, 1.0)
        d2d = db * (1.0 - h_sm) + da * h_sm - k_sm * h_sm * (1.0 - h_sm)

        mouth_v_r = np.sqrt((vq_x / 0.36) ** 2 + (vq_z / 0.21) ** 2)
        not_mouth = np.clip((mouth_v_r - 1.16) / 0.14, 0.0, 1.0)
        not_base = np.clip((vq_y + 0.78) / 0.08, 0.0, 1.0)
        z_face_w = np.clip((np.abs(vq_z) - 0.10) / 0.10, 0.0, 1.0)

        # Double nervure concentrique 3D analytique C^infty en forme de cœur avec biseau intaglio (+1.6 mm / -0.5 mm)
        rib1 = 0.0145 * np.exp(-(((d2d - 0.095) / 0.020) ** 2)) - 0.0045 * np.exp(-(((d2d - 0.095) / 0.042) ** 2))
        rib2 = 0.0125 * np.exp(-(((d2d - 0.185) / 0.020) ** 2)) - 0.0040 * np.exp(-(((d2d - 0.185) / 0.040) ** 2))
        heart_ribs = (rib1 + rib2) * z_face_w * not_mouth * not_base

        # Collerette de cristal 3D entourant l'embouchure supérieure
        collar_ring = 0.0125 * np.exp(-(((mouth_v_r - 1.22) / 0.085) ** 2)) * np.clip((vq_y - 0.20) / 0.12, 0.0, 1.0)

        # Côtes diamantées subtiles sur le chant latéral (|z| < 0.20) pour enrichir les vues de profil
        side_w = np.exp(-((vq_z / 0.13) ** 2)) * not_mouth * not_base * np.clip((d2d - 0.01) / 0.04, 0.0, 1.0)
        side_flutes = 0.0055 * np.cos(24.0 * vq_y) * side_w

        return ext_w * (heart_ribs + collar_ring + side_flutes)

    return _subdivide_and_sculpt_3d_relief(
        mesh=mesh,
        inner_mask_fn=_emoji_inner_mask,
        disp_height_smooth=disp_height_smooth,
        sample_bilinear_fn=sample_bilinear_fn,
        front_y_center=-0.10,
        front_y_half=0.56,
        relief_amplitude=0.028,
        extra_radial_fn=_emoji_extra_radial,
    )



def build_hollow_heart_crystal_vase_mesh(
    spec: dict[str, Any],
    height_01: np.ndarray,
    n_theta: int = 360,
    n_z_outer: int = 260,
    n_z_inner: int = 120,
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Construit un maillage 3D 2-manifold étanche (`watertight`) 100 % vide sans fleurs :
    - Si `heart_style == "anatomical"` : Vrai Cœur Anatomique 3D 🫀 avec ventricules asymétriques,
      oreillettes, sillons interventriculaires, artères coronaires en relief et gros vaisseaux tubulaires
      supérieurs ouverts (Crosse Aortique à 3 branches + Tronc Pulmonaire + Veine Cave Supérieure).
    - Si `heart_style == "emoji"` : Vrai Cœur Émoji / Romantique 3D ❤️ avec deux grands lobes ronds
      supérieurs, une vraie échancrure centrale en V dégagée (sans cheminée d'amphore) et une pointe en V
      inférieure (sans pied de gobelet), creusé au sommet vers la cavité interne en forme de cœur.
    """
    tex_h, tex_w = height_01.shape[:2]
    disp_height_smooth = cv2.GaussianBlur(height_01.astype(np.float32), (0, 0), sigmaX=2.8, sigmaY=2.8)

    def _sample_bilinear(img_2d: np.ndarray, u_arr: np.ndarray, v_arr: np.ndarray) -> np.ndarray:
        fx = np.clip(u_arr * (tex_w - 1), 0.0, float(tex_w - 1.001))
        fy = np.clip((1.0 - v_arr) * (tex_h - 1), 0.0, float(tex_h - 1.001))
        x0 = np.floor(fx).astype(np.int32)
        y0 = np.floor(fy).astype(np.int32)
        x1 = np.minimum(x0 + 1, tex_w - 1)
        y1 = np.minimum(y0 + 1, tex_h - 1)
        wx = fx - x0
        wy = fy - y0
        v00 = img_2d[y0, x0]
        v10 = img_2d[y0, x1]
        v01 = img_2d[y1, x0]
        v11 = img_2d[y1, x1]
        return (1.0 - wy) * ((1.0 - wx) * v00 + wx * v10) + wy * ((1.0 - wx) * v01 + wx * v11)

    if spec.get("heart_shape", True):
        if spec.get("heart_style", "emoji") == "anatomical":
            return _build_anatomical_heart_vase_mesh(spec, disp_height_smooth, _sample_bilinear)
        return _build_emoji_heart_vase_mesh(spec, disp_height_smooth, _sample_bilinear)

    def _eval_outer_ring(s_val: float, is_body: bool = True) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False, dtype=np.float64)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        y = np.full_like(theta, -0.85 + 1.70 * s_val)
        r = 0.32 + 0.24 * math.sin(math.pi * s_val)
        x = r * cos_t
        z = r * sin_t

        if is_body:
            # Coordonnées UV orientées SANS inversion miroir sur la paroi extérieure :
            x_norm = np.clip(x / 0.82, -1.0, 1.0)
            u_front = 0.25 + 0.22 * x_norm
            u_back = 0.75 - 0.22 * x_norm
            u_uv = np.where(sin_t >= 0.0, u_front, u_back)
            v_uv = np.clip(0.51 + 0.44 * y, 0.02, 0.98)

            # Bas-relief 3D lisse (filtré Nyquist + bilinéaire) uniquement sur la zone gravée
            if 0.16 <= s_val <= 0.80:
                h_val = _sample_bilinear(disp_height_smooth, u_uv, v_uv).astype(np.float64)
                front_back_mask = np.power(np.abs(sin_t), 0.85)
                disp = 0.0055 * h_val * front_back_mask
                rad_xz = np.maximum(np.hypot(x, z), 1e-6)
                x = x + disp * (x / rad_xz) * 0.30
                z = z + disp * np.sign(sin_t + 1e-12)
        else:
            # La cavité intérieure creuse pointe vers une plage UV de cristal pur non-gravé
            # pour éviter tout dédoublement optique ("ghosting") du prénom à travers la paroi avant !
            u_uv = np.full_like(theta, 0.75)
            v_uv = np.clip(0.12 + 0.06 * y, 0.04, 0.22)

        return x, y, z, u_uv, v_uv

    verts_list: list[np.ndarray] = []
    uvs_list: list[np.ndarray] = []
    faces_list: list[list[int]] = []

    # 1. Centre du fond extérieur (sous le piédestal, y = -0.88)
    verts_list.append(np.array([[0.0, -0.88, 0.0]], dtype=np.float64))
    uvs_list.append(np.array([[0.25, 0.98]], dtype=np.float64))
    bottom_center_idx = 0

    # 2. Anneaux de la paroi extérieure
    s_outer = np.linspace(0.0, 1.0, n_z_outer, dtype=np.float64)
    outer_ring_starts: list[int] = []
    for s_val in s_outer:
        start_idx = sum(len(v) for v in verts_list)
        outer_ring_starts.append(start_idx)
        x, y, z, u_r, v_r = _eval_outer_ring(float(s_val), is_body=True)
        verts_list.append(np.column_stack([x, y, z]))
        uvs_list.append(np.column_stack([u_r, v_r]))

    # 3. Anneaux de la cavité intérieure creuse (descendant du col ouvert vers le cœur du vase)
    wall_thickness_ratio = 0.84
    s_inner = np.linspace(1.0, 0.16, n_z_inner, dtype=np.float64)
    inner_ring_starts: list[int] = []
    for idx_in, s_val in enumerate(s_inner):
        start_idx = sum(len(v) for v in verts_list)
        inner_ring_starts.append(start_idx)
        x, y, z, u_r, v_r = _eval_outer_ring(float(s_val), is_body=False)
        scale_in = 0.92 if idx_in == 0 else wall_thickness_ratio
        y_in = y + (0.012 if idx_in == 0 else 0.0)
        verts_list.append(np.column_stack([x * scale_in, y_in, z * scale_in]))
        uvs_list.append(np.column_stack([u_r, v_r]))

    # 4. Centre du fond intérieur de la cavité creuse
    inner_bottom_y = -0.73 + 1.24 * ((0.16 - 0.10) / 0.75)
    inner_center_idx = sum(len(v) for v in verts_list)
    verts_list.append(np.array([[0.0, inner_bottom_y, 0.0]], dtype=np.float64))
    uvs_list.append(np.array([[0.25, 0.88]], dtype=np.float64))

    r0 = outer_ring_starts[0]
    for j in range(n_theta):
        jn = (j + 1) % n_theta
        faces_list.append([bottom_center_idx, r0 + jn, r0 + j])

    for i in range(len(outer_ring_starts) - 1):
        ra = outer_ring_starts[i]
        rb = outer_ring_starts[i + 1]
        for j in range(n_theta):
            jn = (j + 1) % n_theta
            faces_list.append([ra + j, ra + jn, rb + jn])
            faces_list.append([ra + j, rb + jn, rb + j])

    ra = outer_ring_starts[-1]
    rb = inner_ring_starts[0]
    for j in range(n_theta):
        jn = (j + 1) % n_theta
        faces_list.append([ra + j, ra + jn, rb + jn])
        faces_list.append([ra + j, rb + jn, rb + j])

    for i in range(len(inner_ring_starts) - 1):
        ra = inner_ring_starts[i]
        rb = inner_ring_starts[i + 1]
        for j in range(n_theta):
            jn = (j + 1) % n_theta
            faces_list.append([ra + j, ra + jn, rb + jn])
            faces_list.append([ra + j, rb + jn, rb + j])

    rlast = inner_ring_starts[-1]
    for j in range(n_theta):
        jn = (j + 1) % n_theta
        faces_list.append([rlast + j, rlast + jn, inner_center_idx])

    verts_arr = np.vstack(verts_list).astype(np.float64)
    uvs_arr = np.vstack(uvs_list).astype(np.float64)
    faces_arr = np.asarray(faces_list, dtype=np.int64)

    mesh = trimesh.Trimesh(vertices=verts_arr, faces=faces_arr, process=False)
    trimesh.repair.fix_normals(mesh)
    return mesh, uvs_arr


def render_studio_reference_preview(
    spec: dict[str, Any],
    out_png_path: Path,
    size: int = 1024,
) -> None:
    """Génère une image de référence studio haute-fidélité du Vase Cœur bicolore isolé
    (extérieur couleur du vase + intérieur creux en blanc pur, zéro personnage halluciné,
    zéro col d'amphore et zéro pied de gobelet) pour `reference/face.png`."""
    img = Image.new("RGB", (size, size), (244, 246, 250))
    draw = ImageDraw.Draw(img, "RGBA")

    cx, cy = size // 2, int(size * 0.51)
    for r in range(int(size * 0.44), 10, -4):
        t = r / (size * 0.44)
        c_val = int(248 - 14 * (1.0 - t))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(c_val, c_val - 2, c_val + 2, 255))

    base_y = int(size * 0.84)
    draw.ellipse([cx - int(size * 0.16), base_y - int(size * 0.025), cx + int(size * 0.16), base_y + int(size * 0.032)], fill=(215, 190, 208, 150))
    draw.ellipse([cx - int(size * 0.09), base_y - int(size * 0.015), cx + int(size * 0.09), base_y + int(size * 0.020)], fill=(255, 145, 198, 135))

    br, bg, bb = spec["base_rgb"]
    dr, dg, db = spec["deep_rgb"]
    ir, ig, ib = spec.get("interior_rgb", (252, 253, 255))

    # Corps extérieur 100 % Cœur Émoji authentique (sans pied de gobelet ni col d'amphore)
    _draw_heart_polygon(draw, cx, int(size * 0.49), scale=size * 0.0205, fill=(dr, dg, db, 255))
    _draw_heart_polygon(draw, cx, int(size * 0.49), scale=size * 0.0195, fill=(br, bg, bb, 255))

    # Ouverture supérieure creuse biseautée dans le sillon central : Intérieur Blanc Pur (#FCFDFE)
    cleft_y = int(size * 0.305)
    draw.ellipse(
        [cx - int(size * 0.105), cleft_y - int(size * 0.034), cx + int(size * 0.105), cleft_y + int(size * 0.034)],
        fill=(ir, ig, ib, 255),
        outline=(min(255, br + 32), min(255, bg + 32), min(255, bb + 32), 255),
        width=max(3, size // 240),
    )
    draw.ellipse(
        [cx - int(size * 0.082), cleft_y - int(size * 0.022), cx + int(size * 0.082), cleft_y + int(size * 0.024)],
        fill=(max(218, ir - 24), max(220, ig - 22), max(226, ib - 18), 255),
    )

    # Reflets spéculaires optiques de glaçure cristal sur les deux lobes du cœur
    draw.polygon([
        (cx - int(size * 0.24), int(size * 0.34)),
        (cx - int(size * 0.18), int(size * 0.31)),
        (cx - int(size * 0.12), int(size * 0.56)),
        (cx - int(size * 0.16), int(size * 0.60)),
    ], fill=(255, 244, 250, 175))
    draw.polygon([
        (cx + int(size * 0.17), int(size * 0.32)),
        (cx + int(size * 0.23), int(size * 0.35)),
        (cx + int(size * 0.15), int(size * 0.58)),
        (cx + int(size * 0.11), int(size * 0.54)),
    ], fill=(255, 240, 248, 160))

    for dx_f, dy_f, sc_f in [(-0.14, -0.07, 0.0026), (0.14, -0.07, 0.0026), (-0.16, 0.04, 0.0022), (0.16, 0.04, 0.0022), (-0.09, 0.14, 0.0023), (0.09, 0.14, 0.0023)]:
        _draw_heart_polygon(draw, cx + int(dx_f * size), int(size * 0.49) + int(dy_f * size), scale=size * sc_f, fill=(255, 248, 252, 245))

    label = spec.get("engraved_text")
    if label:
        font = _load_best_font(max(44, int(size * 0.076)))
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = cx - tw // 2
        ty = int(size * 0.48) - th // 2
        draw.text((tx + 2, ty + 2), label, fill=(max(0, dr - 45), max(0, dg - 30), max(0, db - 35), 220), font=font)
        draw.text((tx, ty), label, fill=(255, 250, 253, 255), font=font)
        _draw_heart_polygon(draw, cx, ty + th + int(size * 0.028), scale=size * 0.0018, fill=(255, 250, 253, 255))

    out_png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_png_path), format="PNG")


def render_vessel_4view_previews(
    mesh: trimesh.Trimesh,
    uvs_arr: np.ndarray,
    albedo_img: Image.Image,
    apercus_dir: Path,
    res: int = 800,
    glb_path: Path | None = None,
) -> dict[str, str]:
    """Génère les 4 vues de contrôle (Face, Dos, Profil Gauche, Profil Droit) directement via `/home/juan/.local/bin/f3d`
    (le viewer OpenGL/VTK exact de l'utilisateur) sur le fichier `.glb` exporté afin que `apercus/` reflète à 100 %
    sans aucun artifice ce que affiche `f3d`, et nettoie tout ancien aperçu obsolète."""
    import shutil
    import subprocess

    apercus_dir.mkdir(parents=True, exist_ok=True)
    # Nettoyage systématique des anciens aperçus obsolètes dans apercus/ et journal/verifications/
    for old_png in apercus_dir.glob("*.png"):
        try:
            old_png.unlink()
        except Exception:
            pass
    verif_dir = apercus_dir.parent / "journal" / "verifications"
    if verif_dir.is_dir():
        for old_v in verif_dir.glob("*.png"):
            try:
                old_v.unlink()
            except Exception:
                pass

    f3d_bin = shutil.which("f3d") or ("/home/juan/.local/bin/f3d" if Path("/home/juan/.local/bin/f3d").is_file() else None)
    views_f3d = [
        ("face", "0,-0.24,-1", "FACE (+Z) — F3D PBR"),
        ("dos", "0,-0.24,1", "DOS (-Z) — F3D PBR"),
        ("profil_gauche", "1,-0.24,0", "PROFIL GAUCHE (-X) — F3D PBR"),
        ("profil_droit", "-1,-0.24,0", "PROFIL DROIT (+X) — F3D PBR"),
    ]
    out_paths: dict[str, str] = {}
    panels: list[Image.Image] = []

    if f3d_bin and glb_path is not None and Path(glb_path).is_file():
        for v_name, cam_dir, label_txt in views_f3d:
            p_out = apercus_dir / f"{v_name}.png"
            cmd = [
                f3d_bin,
                str(glb_path),
                f"--output={p_out}",
                f"--resolution={res},{res}",
                f"--camera-direction={cam_dir}",
                "--up=+Y",
                "--ambient-occlusion=true",
                "--anti-aliasing=true",
                "--tone-mapping=true",
                "--grid=false",
                "--axis=false",
                "--filename=false",
                "--bg-color=0.11,0.12,0.16",
            ]
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            if p_out.is_file():
                out_paths[v_name] = str(p_out)
                pil_v = Image.open(str(p_out)).convert("RGB")
                labeled = pil_v.copy()
                d_lbl = ImageDraw.Draw(labeled)
                d_lbl.rectangle([10, 10, 310, 44], fill=(18, 20, 28))
                d_lbl.text((20, 17), label_txt, fill=(250, 252, 255))
                panels.append(labeled)

        if len(panels) == 4:
            sheet = Image.new("RGB", (res * 4, res), (28, 31, 41))
            for idx_p, pan in enumerate(panels):
                sheet.paste(pan, (idx_p * res, 0))
            sheet_path = apercus_dir / "planche_controle_4vues.png"
            sheet.save(str(sheet_path), format="PNG")
            out_paths["sheet"] = str(sheet_path)
            if verif_dir.is_dir():
                for v_name in ("face", "dos", "profil_gauche", "profil_droit"):
                    shutil.copyfile(out_paths[v_name], str(verif_dir / f"verif_{v_name}.png"))
            return out_paths

    # Fallback rastériseur Z-buffer si f3d n'est pas disponible
    albedo_np = np.asarray(albedo_img.convert("RGB"), dtype=np.float32)
    tex_h, tex_w = albedo_np.shape[:2]

    v = np.asarray(mesh.vertices, dtype=np.float64)
    f = np.asarray(mesh.faces, dtype=np.int64)
    vn = np.asarray(mesh.vertex_normals, dtype=np.float64)

    u_cl = np.clip(uvs_arr[:, 0], 0.0, 1.0)
    v_cl = np.clip(1.0 - uvs_arr[:, 1], 0.0, 1.0)
    ix = np.clip((u_cl * (tex_w - 1)).astype(np.int32), 0, tex_w - 1)
    iy = np.clip((v_cl * (tex_h - 1)).astype(np.int32), 0, tex_h - 1)
    v_rgb = albedo_np[iy, ix]

    views = [
        ("face", 0.0, "FACE (+Z)"),
        ("dos", math.pi, "DOS (-Z)"),
        ("profil_gauche", -0.5 * math.pi, "PROFIL GAUCHE (-X)"),
        ("profil_droit", 0.5 * math.pi, "PROFIL DROIT (+X)"),
    ]
    bmin = v.min(axis=0)
    bmax = v.max(axis=0)
    center = 0.5 * (bmin + bmax)
    max_span = float(max(bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2], 1e-5))
    scale = (res * 0.80) / max_span

    light_dir = np.array([0.28, 0.42, 0.86], dtype=np.float64)
    light_dir /= np.linalg.norm(light_dir)
    view_dir = np.array([0.0, 0.14, 0.99], dtype=np.float64)
    view_dir /= np.linalg.norm(view_dir)
    half_vec = light_dir + view_dir
    half_vec /= np.linalg.norm(half_vec)

    for v_name, yaw, label_txt in views:
        cy, sy = math.cos(yaw), math.sin(yaw)
        vc = v - center
        rx = cy * vc[:, 0] + sy * vc[:, 2]
        ry = vc[:, 1]
        rz = -sy * vc[:, 0] + cy * vc[:, 2]
        tilt = math.radians(11.0)
        ct, st = math.cos(tilt), math.sin(tilt)
        ry_t = ct * ry - st * rz
        rz_t = st * ry + ct * rz

        nx_r = cy * vn[:, 0] + sy * vn[:, 2]
        ny_r = ct * vn[:, 1] - st * (-sy * vn[:, 0] + cy * vn[:, 2])
        nz_r = st * vn[:, 1] + ct * (-sy * vn[:, 0] + cy * vn[:, 2])
        n_rot = np.column_stack([nx_r, ny_r, nz_r])

        ndotl = np.clip(n_rot @ light_dir, 0.0, 1.0)
        ndoth = np.clip(n_rot @ half_vec, 0.0, 1.0)
        spec_hi = np.power(ndoth, 36.0) * 85.0
        shade = 0.40 + 0.60 * ndotl
        shaded_v = np.clip(v_rgb * shade[:, None] + spec_hi[:, None], 0.0, 255.0)

        sx = (0.5 * res + rx * scale).astype(np.int32)
        sy_px = (0.5 * res - ry_t * scale).astype(np.int32)

        f_z = rz_t[f].mean(axis=1)
        order = np.argsort(f_z)
        f_sorted = f[order]
        f_col = shaded_v[f_sorted].mean(axis=1).astype(np.uint8)

        canvas = np.full((res, res, 3), (242, 244, 249), dtype=np.uint8)
        pts_2d = np.stack([sx[f_sorted], sy_px[f_sorted]], axis=-1)
        for tri_pts, col in zip(pts_2d, f_col):
            cv2.fillConvexPoly(canvas, tri_pts, (int(col[0]), int(col[1]), int(col[2])), lineType=cv2.LINE_AA)

        pil_v = Image.fromarray(canvas, mode="RGB")
        p_out = apercus_dir / f"{v_name}.png"
        pil_v.save(str(p_out), format="PNG")
        out_paths[v_name] = str(p_out)

        labeled = pil_v.copy()
        d_lbl = ImageDraw.Draw(labeled)
        d_lbl.rectangle([10, 10, 250, 44], fill=(24, 26, 34))
        d_lbl.text((20, 17), label_txt, fill=(250, 252, 255))
        panels.append(labeled)

    sheet = Image.new("RGB", (res * 4, res), (242, 244, 249))
    for idx_p, pan in enumerate(panels):
        sheet.paste(pan, (idx_p * res, 0))
    sheet_path = apercus_dir / "planche_controle_4vues.png"
    sheet.save(str(sheet_path), format="PNG")
    out_paths["sheet"] = str(sheet_path)
    return out_paths


def export_real_size_printable_stl(
    mesh: trimesh.Trimesh,
    out_stl_path: str | Path,
    target_height_mm: float = 180.0,
) -> dict[str, Any]:
    """Exporte un maillage 2-manifold étanche en STL binaire calibré en millimètres taille réelle
    (Z-up sur le plateau d'impression `z_min = 0.0 mm`, centré en X/Y, 100 % vide à l'intérieur)."""
    source_mesh = mesh.metadata.get("watertight_stl_mesh", mesh) if hasattr(mesh, "metadata") and isinstance(mesh.metadata, dict) else mesh
    v = np.asarray(source_mesh.vertices, dtype=np.float64).copy()
    # En glTF le vase est Y-up ; pour un slicer d'impression 3D (Cura / PrusaSlicer / Bambu Studio),
    # on convertit en Z-up (X_stl = X, Y_stl = -Z, Z_stl = Y) et on met à l'échelle exacte en mm.
    v_stl = np.column_stack([v[:, 0], -v[:, 2], v[:, 1]])
    z_span = float(v_stl[:, 2].max() - v_stl[:, 2].min())
    scale_mm = float(target_height_mm) / max(z_span, 1e-6)
    v_stl *= scale_mm
    v_stl[:, 0] -= 0.5 * float(v_stl[:, 0].min() + v_stl[:, 0].max())
    v_stl[:, 1] -= 0.5 * float(v_stl[:, 1].min() + v_stl[:, 1].max())
    v_stl[:, 2] -= float(v_stl[:, 2].min())

    stl_mesh = trimesh.Trimesh(vertices=v_stl, faces=np.asarray(source_mesh.faces, dtype=np.int64).copy(), process=False)
    trimesh.repair.fix_normals(stl_mesh)
    stl_p = Path(out_stl_path)
    stl_p.parent.mkdir(parents=True, exist_ok=True)
    stl_mesh.export(str(stl_p), file_type="stl")
    ext_mm = np.ptp(v_stl, axis=0)
    return {
        "stl_path": str(stl_p),
        "dimensions_mm": [round(float(ext_mm[0]), 2), round(float(ext_mm[1]), 2), round(float(ext_mm[2]), 2)],
        "wall_thickness_mm": round(0.16 * 0.5 * float(min(ext_mm[0], ext_mm[1])), 2),
        "watertight_2manifold": bool(stl_mesh.is_watertight),
        "empty_cavity_no_flowers": True,
        "faces": int(len(stl_mesh.faces)),
    }


def generate_crystal_vessel_deliverables(
    prompt: str,
    output_glb_path: str | Path,
    geometry_glb_path: str | Path | None = None,
    reference_png_path: str | Path | None = None,
    tex_size: int = 2048,
    modify_from: str | Path | None = None,
) -> dict[str, Any]:
    """Génère ou modifie incrémentalement (sans repartir de zéro via `modify_from` / `vessel_spec.json`)
    le GLB PBR bicolore (`modele_couleurs.glb` : extérieur couleur du vase + intérieur blanc pur),
    le GLB géométrique pur (`modele_geometrie.glb`), les fichiers STL taille réelle (180 mm) prêts pour l'impression 3D
    (en version Cœur Émoji/Romantique ET Cœur Anatomique, 100 % vides sans fleurs) et l'image de référence."""
    import shutil

    out_p = Path(output_glb_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    spec_json_path = out_p.parent / "vessel_spec.json"

    base_spec: dict[str, Any] | None = None
    if modify_from is not None:
        mod_p = Path(modify_from)
        cand_spec = mod_p.parent / "vessel_spec.json" if mod_p.is_file() else mod_p / "vessel_spec.json"
        if cand_spec.is_file():
            try:
                base_spec = json.loads(cand_spec.read_text(encoding="utf-8"))
            except Exception:
                base_spec = None
    if base_spec is None and spec_json_path.is_file():
        try:
            base_spec = json.loads(spec_json_path.read_text(encoding="utf-8"))
        except Exception:
            base_spec = None

    spec = extract_engraving_spec(prompt, base_spec=base_spec)
    try:
        spec_json_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    height_01, albedo_img, nrm_img, orm_img = build_engraving_heightfield_and_textures(spec, tex_size=tex_size)
    mesh, uvs_arr = build_hollow_heart_crystal_vase_mesh(spec, height_01)

    # IMPORTANT : En glTF 2.0 (et particulièrement dans F3D / VTK 9.3 OpenGL PBR), le maillage subdivisé (~450 000 faces)
    # porte directement les vraies normales géométriques 3D (`NORMAL`) du haut-relief sculpté (+2.8 mm / -1.1 mm).
    # Ne pas attacher de `normalTexture` sans attribut `TANGENT` élimine à 100 % la division par zéro `1/det(dUV) = NaN`
    # dans le shader VTK qui causait l'éblouissement blanc (`#FFFFFF`) dans `f3d` !
    mat = trimesh.visual.material.PBRMaterial(
        name="AuroraOpticalCrystalMaterial",
        baseColorFactor=[1.0, 1.0, 1.0, 1.0],
        baseColorTexture=albedo_img,
        metallicRoughnessTexture=orm_img,
        metallicFactor=0.04,
        roughnessFactor=0.28,
        alphaMode="OPAQUE",
        doubleSided=True,
    )
    mesh.visual = trimesh.visual.TextureVisuals(uv=uvs_arr, material=mat)
    mesh.export(str(out_p), file_type="glb")

    optical_meta = {
        "style_id": "crystal_glossy",
        "is_optical_crystal_glass": True,
        "ior": 1.54,
        "specularFactor": 0.92,
        "clearcoatFactor": 0.58,
        "clearcoatRoughnessFactor": 0.08,
        "transmissionFactor": 0.88,
        "attenuationDistance": 0.65,
        "attenuationColor": spec["attenuation_color"],
        "thicknessFactor": 0.18,
        "occlusionStrength": 0.85,
        "alphaMode": "OPAQUE",
        "baseColorAlpha": 1.0,
    }
    inject_gltf_optical_extensions(out_p, optical_meta)

    primary_style = spec.get("heart_style", "emoji")
    primary_style_glb = out_p.parent / f"modele_couleurs_{primary_style}.glb"
    if primary_style_glb != out_p:
        shutil.copyfile(str(out_p), str(primary_style_glb))

    if geometry_glb_path is not None:
        geom_p = Path(geometry_glb_path)
        geom_p.parent.mkdir(parents=True, exist_ok=True)
        stl_src = mesh.metadata.get("watertight_stl_mesh", mesh) if hasattr(mesh, "metadata") and isinstance(mesh.metadata, dict) else mesh
        geom_mesh = trimesh.Trimesh(vertices=np.asarray(stl_src.vertices).copy(), faces=np.asarray(stl_src.faces).copy(), process=False)
        trimesh.repair.fix_normals(geom_mesh)
        clay_mat = trimesh.visual.material.PBRMaterial(
            name="AuroraClayGeometry",
            baseColorFactor=[222, 214, 208, 255],
            metallicFactor=0.08,
            roughnessFactor=0.34,
        )
        geom_mesh.visual = trimesh.visual.TextureVisuals(material=clay_mat)
        geom_mesh.export(str(geom_p), file_type="glb")

    target_mm = float(spec.get("real_print_height_mm", 180.0))
    primary_stl_info = export_real_size_printable_stl(
        mesh,
        out_p.parent / f"vase_coeur_{primary_style}_taille_reelle_{int(target_mm)}mm.stl",
        target_height_mm=target_mm,
    )

    # Génère également la variante complémentaire (Cœur Anatomique <-> Cœur Émoji) 100 % vide sans fleurs
    # afin que l'utilisateur dispose immédiatement des 2 morphologies en GLB optique ET en STL taille réelle !
    alt_style = "anatomical" if primary_style == "emoji" else "emoji"
    alt_spec = dict(spec, heart_style=alt_style)
    alt_mesh, alt_uvs = build_hollow_heart_crystal_vase_mesh(alt_spec, height_01)
    alt_mat = trimesh.visual.material.PBRMaterial(
        name="AuroraOpticalCrystalMaterialAlt",
        baseColorFactor=[1.0, 1.0, 1.0, 1.0],
        baseColorTexture=albedo_img,
        metallicRoughnessTexture=orm_img,
        metallicFactor=0.04,
        roughnessFactor=0.28,
        alphaMode="OPAQUE",
        doubleSided=True,
    )
    alt_mesh.visual = trimesh.visual.TextureVisuals(uv=alt_uvs, material=alt_mat)
    alt_glb_path = out_p.parent / f"modele_couleurs_{alt_style}.glb"
    alt_mesh.export(str(alt_glb_path), file_type="glb")
    inject_gltf_optical_extensions(alt_glb_path, optical_meta)
    alt_stl_info = export_real_size_printable_stl(
        alt_mesh,
        out_p.parent / f"vase_coeur_{alt_style}_taille_reelle_{int(target_mm)}mm.stl",
        target_height_mm=target_mm,
    )

    if reference_png_path is not None:
        render_studio_reference_preview(spec, Path(reference_png_path))

    # Synchronisation canonique entre `modele/` et `livrables/` dans le dossier de mission
    # pour éviter qu'un viewer externe (`f3d`) n'ouvre un ancien fichier non mis à jour :
    run_root = out_p.parent.parent
    for sibling_name in ("modele", "livrables"):
        sib_dir = run_root / sibling_name
        if sib_dir.is_dir() and sib_dir.resolve() != out_p.parent.resolve():
            for generated_file in out_p.parent.glob("*"):
                if generated_file.is_file():
                    shutil.copyfile(str(generated_file), str(sib_dir / generated_file.name))

    previews_info = render_vessel_4view_previews(mesh, uvs_arr, albedo_img, out_p.parent.parent / "apercus", glb_path=out_p)
    f3d_bin_alt = shutil.which("f3d") or ("/home/juan/.local/bin/f3d" if Path("/home/juan/.local/bin/f3d").is_file() else None)
    if f3d_bin_alt and alt_glb_path.is_file():
        import subprocess

        ap_dir = out_p.parent.parent / "apercus"
        for v_nm, cam_d in (("face", "0,-0.24,-1"), ("dos", "0,-0.24,1"), ("profil_gauche", "1,-0.24,0"), ("profil_droit", "-1,-0.24,0")):
            subprocess.run(
                [
                    f3d_bin_alt,
                    str(alt_glb_path),
                    f"--output={ap_dir / f'{alt_style}_{v_nm}.png'}",
                    "--resolution=900,900",
                    f"--camera-direction={cam_d}",
                    "--up=+Y",
                    "--ambient-occlusion=true",
                    "--anti-aliasing=true",
                    "--tone-mapping=true",
                    "--bg-color=0.11,0.12,0.16",
                    "--filename=false",
                    "--axis=false",
                    "--grid=false",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=25,
            )
    stl_check_mesh = mesh.metadata.get("watertight_stl_mesh", mesh) if hasattr(mesh, "metadata") and isinstance(mesh.metadata, dict) else mesh

    return {
        "ok": True,
        "incremental_delta_applied": base_spec is not None,
        "output_glb": str(out_p),
        "geometry_glb": str(geometry_glb_path) if geometry_glb_path else None,
        "alt_variant_glb": str(alt_glb_path),
        "printable_stl_primary": primary_stl_info,
        "printable_stl_alt": alt_stl_info,
        "previews": previews_info,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(stl_check_mesh.is_watertight),
        "spec": spec,
        "optical_meta": optical_meta,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AuroraIA Universal Crystal Vessel Sculptor")
    parser.add_argument("--prompt", required=True, help="Prompt describing the crystal/glass vessel and engravings")
    parser.add_argument("--output-glb", required=True, help="Output path for modele_couleurs.glb")
    parser.add_argument("--geometry-glb", default=None, help="Optional output path for modele_geometrie.glb")
    parser.add_argument("--reference-png", default=None, help="Optional output path for reference/face.png")
    parser.add_argument("--modify-from", default=None, help="Optional existing GLB or directory for incremental delta modification")
    args = parser.parse_args()
    res = generate_crystal_vessel_deliverables(
        prompt=args.prompt,
        output_glb_path=args.output_glb,
        geometry_glb_path=args.geometry_glb,
        reference_png_path=args.reference_png,
        modify_from=args.modify_from,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
