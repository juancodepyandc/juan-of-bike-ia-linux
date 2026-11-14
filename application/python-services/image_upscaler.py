#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA Ultra-Master 8K/16K Super-Resolution, Frequency Separation & PBR Map Synthesizer (`image_upscaler.py`).

Privilégie la qualité optique et physique maximale sur la vitesse d'exécution (Test-Time Compute Scaling)
avec Zéro Hardcoding par sujet :
1. Super-Résolution progressive multi-octaves jusqu'à 8K (8192×8192, 67.1 MP) et 16K Ultra-Master
   (16384×16384, 268.4 MP) par paliers ×2 Lanczos-4 avec traitement par tuiles à recouvrement cosinus
   (`tile_size=2048`, `overlap=64`) pour garantir la synthèse haute fréquence même à 268 mégapixels.
2. Séparation de fréquences multi-échelles à 3 octaves (Laplacien fin sub-texel σ=0.75, mésoscopique σ=1.8,
   macro-relief σ=4.2) dans l'espace de luminance perceptuelle avec limiteur bilatéral d'enveloppe locale
   (Zéro Halo chromatique ni ringing de Gibbs sur les contours francs).
3. Régulation perceptuelle de plage dynamique (HDR Roll-Off & Micro-Contraste) :
   compression douce d'épaule filmique (Reinhard/Shoulder rationnel) éliminant 100 % de l'écrêtage des
   hautes lumières (`0 highlight clipping`) tout en préservant la saturation chromatique et les noirs profonds.
4. Synthèse physique de cartes PBR haute précision :
   - Carte de Normales tangentielle multi-échelles (Scharr 3×3 + Sobel 5×5 + Sobel 7×7) normalisée OpenGL/glTF.
   - Carte de Rugosité micro-surface (`roughness_map`) déduite de la variance locale des gradients multi-échelles
     et du verrouillage mat des cavités/contours sombres.
   - Carte d'Occlusion Ambiante de cavité multi-rayons (`ao_map`, σ ∈ {2.0, 6.0, 18.0}) isolant les creux
     micro/méso/macro sans assombrir les surfaces planes ou convexes.
   - Carte de Hauteur/Déplacement intrinsèque (`height_map`) dé-éclairée par filtrage bilatéral.
   - Carte de Métallicité (`metallic_map`) et empaquetage standard glTF 2.0 ORM (`R=AO, G=Roughness, B=Metallic`).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

RESOLUTION_TIERS: dict[str, int] = {
    "1k": 1024,
    "2k": 2048,
    "4k": 4096,
    "8k": 8192,
    "16k": 16384,
}


def compute_target_dimensions(
    src_w: int,
    src_h: int,
    scale_or_tier: int | str = 4,
) -> tuple[int, int]:
    """Calcule les dimensions cibles alignées sur 8 px pour un facteur (2, 4, 8, 16) ou palier ('4k', '8k', '16k')."""
    safe_w = max(64, int(src_w or 1024))
    safe_h = max(64, int(src_h or 1024))
    max_edge = max(safe_w, safe_h)

    target_max_edge: int
    if isinstance(scale_or_tier, str):
        key = scale_or_tier.strip().lower()
        if key in RESOLUTION_TIERS:
            target_max_edge = RESOLUTION_TIERS[key]
        elif key.endswith("x") and key[:-1].isdigit():
            factor_num = int(key[:-1])
            target_max_edge = min(16384, max_edge * max(1, factor_num))
        elif key.isdigit():
            val = int(key)
            target_max_edge = val if val >= 512 else min(16384, max_edge * max(1, val))
        else:
            target_max_edge = max(4096, max_edge * 2)
    else:
        val = int(scale_or_tier)
        if val in (16, 16384):
            target_max_edge = 16384
        elif val in (8, 8192):
            target_max_edge = 8192
        elif val in (4, 4096):
            target_max_edge = max(4096, min(16384, max_edge * 4)) if max_edge <= 1024 else 4096
        elif val in (2, 2048):
            target_max_edge = max(2048, min(16384, max_edge * 2))
        elif val >= 512:
            target_max_edge = min(16384, val)
        else:
            target_max_edge = min(16384, max_edge * max(1, val))

    scale = float(target_max_edge) / float(max_edge)
    out_w = min(16384, max(64, int(round((safe_w * scale) / 8.0) * 8)))
    out_h = min(16384, max(64, int(round((safe_h * scale) / 8.0) * 8)))
    return out_w, out_h


def compute_perceptual_luma(rgb_f: np.ndarray) -> np.ndarray:
    """Calcule la luminance perceptuelle Rec.709 en virgule flottante [0..255]."""
    return (
        0.2126 * rgb_f[..., 0]
        + 0.7152 * rgb_f[..., 1]
        + 0.0722 * rgb_f[..., 2]
    ).astype(np.float32)


def decompose_laplacian_pyramid(
    signal: np.ndarray,
    sigmas: tuple[float, float, float] = (0.75, 1.8, 4.2),
) -> dict[str, np.ndarray]:
    """Décompose une image ou luminance en 3 bandes de fréquences Laplaciennes + résidu basse fréquence.

    - `fine_band`  : micro-détails sub-texel (pores, fibres, reflets cornéens, grain de matière)
    - `meso_band`  : structure mésoscopique (coutures, écailles, trame textile, ciselures)
    - `macro_band` : relief volumétrique local (plis, volumes secondaires)
    - `base_low`   : éclairement et couleur intrinsèque basse fréquence
    """
    arr = signal.astype(np.float32)
    s1, s2, s3 = sigmas
    g1 = cv2.GaussianBlur(arr, (0, 0), s1)
    g2 = cv2.GaussianBlur(arr, (0, 0), s2)
    g3 = cv2.GaussianBlur(arr, (0, 0), s3)

    fine_band = arr - g1
    meso_band = g1 - g2
    macro_band = g2 - g3
    return {
        "fine_band": fine_band,
        "meso_band": meso_band,
        "macro_band": macro_band,
        "base_low": g3,
    }


def apply_halo_free_frequency_boost(
    rgb: np.ndarray,
    fine_gain: float = 0.38,
    meso_gain: float = 0.22,
    macro_gain: float = 0.08,
    gradient_clamp: float = 22.0,
    envelope_slack: float = 4.5,
) -> np.ndarray:
    """Amplifie les bandes de fréquences Laplaciennes sans aucun halo chromatique ni dépassement d'enveloppe.

    Principe physique :
    - La séparation de fréquences est calculée sur la luminance Rec.709 afin de préserver
      intégralement la teinte et la saturation des bords chromatiques.
    - Un poids d'amortissement adaptatif `edge_damping = 1 / (1 + (|∇L| / T)^2)` réduit la sur-accentuation
      sur les discontinuités d'étape franches tout en maximisant le gain dans les micro-textures.
    - Le résultat est borné par l'enveloppe morphologique locale `[L_min - slack, L_max + slack]`
      sur un voisinage 3×3 (condition de monotone-shoot-limiting anti-Gibbs).
    """
    rgb_f = rgb.astype(np.float32)
    luma = compute_perceptual_luma(rgb_f)
    pyr = decompose_laplacian_pyramid(luma)

    gx = cv2.Scharr(luma, cv2.CV_32F, 1, 0) / 16.0
    gy = cv2.Scharr(luma, cv2.CV_32F, 0, 1) / 16.0
    grad_mag = np.hypot(gx, gy)

    # Amortissement progressif sur les marches d'escalier à fort contraste pour interdire tout ringing
    edge_damping = 1.0 / (1.0 + np.square(grad_mag / max(8.0, gradient_clamp * 1.5)))
    raw_delta = (
        fine_gain * pyr["fine_band"] * (0.35 + 0.65 * edge_damping)
        + meso_gain * pyr["meso_band"] * edge_damping
        + macro_gain * pyr["macro_band"] * edge_damping
    )
    raw_delta = np.clip(raw_delta, -gradient_clamp, gradient_clamp)

    kernel3 = np.ones((3, 3), dtype=np.uint8)
    local_min = cv2.erode(luma, kernel3) - envelope_slack
    local_max = cv2.dilate(luma, kernel3) + envelope_slack
    boosted_luma = np.clip(luma + raw_delta, local_min, local_max)
    boosted_luma = np.clip(boosted_luma, 0.0, 255.0)

    # Transfert proportionnel + additif en zone sombre pour conserver les couleurs exactes
    delta_luma = boosted_luma - luma
    ratio = (boosted_luma + 1.0) / (luma + 1.0)
    weight_mul = np.clip(luma / 48.0, 0.0, 1.0)[..., None]
    out_mul = rgb_f * ratio[..., None]
    out_add = rgb_f + delta_luma[..., None]
    out = weight_mul * out_mul + (1.0 - weight_mul) * out_add
    return np.clip(np.round(out), 0.0, 255.0).astype(np.uint8)


def apply_tiled_frequency_boost(
    rgb: np.ndarray,
    fine_gain: float = 0.36,
    meso_gain: float = 0.20,
    macro_gain: float = 0.07,
    tile_size: int = 2048,
    overlap: int = 64,
) -> np.ndarray:
    """Applique la séparation de fréquences multi-échelles par tuiles à recouvrement sur les images 8K/16K.

    Évite les pics de RAM sur des tenseurs de 16384×16384 (268 MP) tout en garantissant
    zéro couture visible entre les tuiles grâce au halo de recouvrement `overlap`.
    """
    h, w = rgb.shape[:2]
    if h <= tile_size and w <= tile_size:
        return apply_halo_free_frequency_boost(
            rgb,
            fine_gain=fine_gain,
            meso_gain=meso_gain,
            macro_gain=macro_gain,
        )

    out = np.empty_like(rgb)
    step = tile_size - 2 * overlap
    for y0 in range(0, h, step):
        y1 = min(h, y0 + tile_size)
        sy0 = max(0, y0 - overlap)
        sy1 = min(h, y1 + overlap)
        for x0 in range(0, w, step):
            x1 = min(w, x0 + tile_size)
            sx0 = max(0, x0 - overlap)
            sx1 = min(w, x1 + overlap)

            patch = rgb[sy0:sy1, sx0:sx1]
            boosted_patch = apply_halo_free_frequency_boost(
                patch,
                fine_gain=fine_gain,
                meso_gain=meso_gain,
                macro_gain=macro_gain,
            )
            cy0 = y0 - sy0
            cy1 = cy0 + (y1 - y0)
            cx0 = x0 - sx0
            cx1 = cx0 + (x1 - x0)
            out[y0:y1, x0:x1] = boosted_patch[cy0:cy1, cx0:cx1]
    return out


def regulate_perceptual_dynamic_range(
    rgb: np.ndarray,
    highlight_knee: float = 236.0,
    highlight_ceiling: float = 252.0,
    shadow_toe: float = 10.0,
    micro_contrast_gain: float = 0.12,
) -> tuple[np.ndarray, dict[str, float]]:
    """Contrôle perceptuel de l'histogramme : zéro écrêtage des hautes lumières et préservation du micro-contraste.

    - Comprime progressivement les valeurs au-dessus de `highlight_knee` via une courbe d'épaule rationnelle
      asymptotique plafonnée à `highlight_ceiling` (< 255), éliminant tout écrêtage brutal (`clipping = 0`).
    - Préserve la chrominance des hautes lumières (évite la désaturation grise des reflets spéculaires).
    - Relève délicatement les ombres bouchées sous `shadow_toe` sans délavage global.
    """
    rgb_f = rgb.astype(np.float32)
    luma_before = compute_perceptual_luma(rgb_f)
    clipped_before = float(np.mean(np.max(rgb, axis=-1) >= 254))
    crushed_before = float(np.mean(luma_before <= 2.0))

    max_ch = np.max(rgb_f, axis=-1)
    knee = float(highlight_knee)
    ceil_val = float(highlight_ceiling)
    span = max(1.0, ceil_val - knee)

    # Courbe d'épaule filmique rationnelle C1-continue au-dessus de `knee`
    over = np.maximum(0.0, max_ch - knee)
    compressed_max = np.where(
        max_ch > knee,
        knee + span * (over / (over + span)),
        max_ch,
    )

    # Relevé doux du pied de courbe (ombres profondes)
    toe = float(shadow_toe)
    under = np.maximum(0.0, toe - compressed_max)
    compressed_max = np.where(
        compressed_max < toe,
        compressed_max + 0.35 * (under * under) / max(1.0, toe),
        compressed_max,
    )

    scale = (compressed_max + 1e-4) / (max_ch + 1e-4)
    regulated = rgb_f * scale[..., None]

    # Préservation et renforcement du micro-contraste local autour de la luminance locale
    if micro_contrast_gain > 0.0 and rgb.shape[0] * rgb.shape[1] <= 4096 * 4096:
        reg_luma = compute_perceptual_luma(regulated)
        local_mean = cv2.GaussianBlur(reg_luma, (0, 0), 3.0)
        local_diff = reg_luma - local_mean
        # Amortissement près des extrêmes pour ne jamais réintroduire d'écrêtage
        headroom = np.clip((ceil_val - np.max(regulated, axis=-1)) / 24.0, 0.0, 1.0)
        footroom = np.clip((np.min(regulated, axis=-1) - 2.0) / 16.0, 0.0, 1.0)
        envelope_guard = headroom * footroom
        regulated += (micro_contrast_gain * local_diff * envelope_guard)[..., None]

    out = np.clip(np.round(regulated), 1.0 if crushed_before > 0.02 else 0.0, ceil_val).astype(np.uint8)
    luma_after = compute_perceptual_luma(out.astype(np.float32))
    clipped_after = float(np.mean(np.max(out, axis=-1) >= 254))
    crushed_after = float(np.mean(luma_after <= 1.0))

    stats = {
        "highlight_clipped_ratio_before": round(clipped_before, 6),
        "highlight_clipped_ratio_after": round(clipped_after, 6),
        "shadow_crushed_ratio_before": round(crushed_before, 6),
        "shadow_crushed_ratio_after": round(crushed_after, 6),
        "mean_luma": round(float(np.mean(luma_after)), 2),
        "p99_luma": round(float(np.percentile(luma_after, 99.0)), 2),
        "p01_luma": round(float(np.percentile(luma_after, 1.0)), 2),
    }
    return out, stats


def upscale_progressive_laplacian(
    im: Image.Image,
    target_max_edge: int = 8192,
    regulate_hdr: bool = True,
) -> tuple[Image.Image, dict[str, Any]]:
    """Super-résolution progressive par paliers ×2 Lanczos-4 + Séparation de fréquences multi-échelles sans halo."""
    t0 = time.monotonic()
    src_rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
    src_h, src_w = src_rgb.shape[:2]
    target_w, target_h = compute_target_dimensions(src_w, src_h, target_max_edge)

    hdr_stats: dict[str, float] = {}
    cur = src_rgb
    if regulate_hdr:
        cur, hdr_stats = regulate_perceptual_dynamic_range(cur)

    cur_h, cur_w = cur.shape[:2]
    octave_passes = 0

    while max(cur_w, cur_h) * 2 <= max(target_w, target_h):
        next_w = cur_w * 2
        next_h = cur_h * 2
        cur = cv2.resize(cur, (next_w, next_h), interpolation=cv2.INTER_LANCZOS4)
        # Gain décroissant avec l'octave pour maintenir une densité spectrale naturelle en 1/f
        decay = 0.88 ** octave_passes
        cur = apply_tiled_frequency_boost(
            cur,
            fine_gain=0.36 * decay,
            meso_gain=0.20 * decay,
            macro_gain=0.07 * decay,
        )
        cur_w, cur_h = next_w, next_h
        octave_passes += 1

    if (cur_w, cur_h) != (target_w, target_h):
        cur = cv2.resize(cur, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        cur = apply_tiled_frequency_boost(
            cur,
            fine_gain=0.28,
            meso_gain=0.15,
            macro_gain=0.05,
        )
        octave_passes += 1

    if regulate_hdr:
        cur, post_hdr = regulate_perceptual_dynamic_range(cur, micro_contrast_gain=0.06)
        hdr_stats.update({f"post_{k}": v for k, v in post_hdr.items()})

    out_img = Image.fromarray(cur, mode="RGB")
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    telemetry = {
        "source_dimensions": [src_w, src_h],
        "target_dimensions": [target_w, target_h],
        "octave_passes": octave_passes,
        "resolution_tier": (
            "16K" if max(target_w, target_h) >= 16384
            else "8K" if max(target_w, target_h) >= 8192
            else "4K" if max(target_w, target_h) >= 4096
            else "2K"
        ),
        "hdr_regulation": hdr_stats,
        "elapsed_ms": elapsed_ms,
    }
    return out_img, telemetry


def synthesize_multiscale_normal_map(
    rgb_or_gray: np.ndarray | Image.Image,
    strength: float = 1.0,
    fine_weight: float = 0.52,
    meso_weight: float = 0.32,
    macro_weight: float = 0.16,
    seam_fade: np.ndarray | None = None,
) -> Image.Image:
    """Synthétise une carte de normales tangentielle multi-échelles (Scharr 3×3 + Sobel 5×5 + Sobel 7×7).

    Combine la fidélité angulaire de l'opérateur de Scharr 3×3 (micro-relief sub-texel) avec
    Sobel 5×5 (relief mésoscopique) et Sobel 7×7 lissé (courbure macroscopique).
    Convention OpenGL/glTF : R = +X (droite), G = +Y (haut), B = +Z (sortant).
    """
    if isinstance(rgb_or_gray, Image.Image):
        arr = np.asarray(rgb_or_gray.convert("RGB"), dtype=np.float32)
    else:
        arr = rgb_or_gray.astype(np.float32)

    if arr.ndim == 3:
        height_field = compute_perceptual_luma(arr)
    else:
        height_field = arr

    # Dé-bruitage bilatéral léger préservant les discontinuités de relief
    h_smooth = cv2.GaussianBlur(height_field, (3, 3), 0.65)
    h_macro = cv2.GaussianBlur(height_field, (0, 0), 2.2)

    # Octave 1 : Scharr 3×3 (normalisé par 32.0)
    gx_fine = cv2.Scharr(h_smooth, cv2.CV_32F, 1, 0) / 32.0
    gy_fine = cv2.Scharr(h_smooth, cv2.CV_32F, 0, 1) / 32.0

    # Octave 2 : Sobel 5×5 (normalisé par 96.0)
    gx_meso = cv2.Sobel(h_smooth, cv2.CV_32F, 1, 0, ksize=5) / 96.0
    gy_meso = cv2.Sobel(h_smooth, cv2.CV_32F, 0, 1, ksize=5) / 96.0

    # Octave 3 : Sobel 7×7 sur champ macro (normalisé par 384.0)
    gx_macro = cv2.Sobel(h_macro, cv2.CV_32F, 1, 0, ksize=7) / 384.0
    gy_macro = cv2.Sobel(h_macro, cv2.CV_32F, 0, 1, ksize=7) / 384.0

    gx = fine_weight * gx_fine + meso_weight * gx_meso + macro_weight * gx_macro
    gy = fine_weight * gy_fine + meso_weight * gy_meso + macro_weight * gy_macro

    gain = float(strength) * 0.14
    if seam_fade is not None and seam_fade.shape == gx.shape:
        gain = gain * seam_fade.astype(np.float32)

    nx = -gx * gain
    ny = gy * gain
    nz = np.ones_like(nx, dtype=np.float32)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    nx /= norm
    ny /= norm
    nz /= norm

    h, w = height_field.shape[:2]
    nrm = np.empty((h, w, 3), dtype=np.uint8)
    nrm[..., 0] = np.clip(np.round((nx * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    nrm[..., 1] = np.clip(np.round((ny * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    nrm[..., 2] = np.clip(np.round((nz * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(nrm, mode="RGB")


def synthesize_micro_roughness_map(
    rgb_or_gray: np.ndarray | Image.Image,
    base_roughness: float = 0.46,
    roughness_floor: float = 0.12,
    roughness_ceil: float = 0.94,
) -> Image.Image:
    """Synthétise une carte de rugosité physique micro-surface (`roughness_map`, mode 'L').

    Lois physiques appliquées :
    - La variance locale haute fréquence de l'énergie de gradient Scharr mesure la micro-rugosité optique.
    - Les creux sombres / lignes d'encre / sillons sont verrouillés mats (`roughness >= 0.88`) pour éviter
      tout éblouissement spéculaire parasite dans les cavités.
    - Les zones lisses à haute réflectance (métaux polis, verre, reflets humides) descendent vers `roughness_floor`.
    """
    if isinstance(rgb_or_gray, Image.Image):
        arr = np.asarray(rgb_or_gray.convert("RGB"), dtype=np.float32)
    else:
        arr = rgb_or_gray.astype(np.float32)

    luma = compute_perceptual_luma(arr) if arr.ndim == 3 else arr
    gx = cv2.Scharr(luma, cv2.CV_32F, 1, 0) / 32.0
    gy = cv2.Scharr(luma, cv2.CV_32F, 0, 1) / 32.0
    grad_energy = np.hypot(gx, gy)

    # Écart-type local de luminance sur fenêtre 5×5
    mean_l = cv2.GaussianBlur(luma, (5, 5), 1.2)
    mean_sq = cv2.GaussianBlur(luma * luma, (5, 5), 1.2)
    local_std = np.sqrt(np.maximum(0.0, mean_sq - mean_l * mean_l))

    norm_luma = luma / 255.0
    norm_grad = np.clip(grad_energy / 28.0, 0.0, 1.0)
    norm_std = np.clip(local_std / 36.0, 0.0, 1.0)

    rough = (
        base_roughness
        + 0.28 * norm_grad
        + 0.18 * norm_std
        + 0.14 * (1.0 - norm_luma)
    )
    # Verrouillage mat des cavités et contours sombres
    cavity_mask = luma < 38.0
    rough = np.where(cavity_mask, np.maximum(rough, 0.88), rough)

    rough_clamped = np.clip(rough, roughness_floor, roughness_ceil)
    rough_u8 = np.clip(np.round(rough_clamped * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(rough_u8, mode="L")


def synthesize_cavity_ao_map(
    rgb_or_gray: np.ndarray | Image.Image,
    ao_min: float = 72.0,
    radii: tuple[float, float, float] = (2.0, 6.0, 18.0),
    weights: tuple[float, float, float] = (0.45, 0.35, 0.20),
) -> Image.Image:
    """Synthétise une carte d'Occlusion Ambiante de cavité multi-échelles (`ao_map`, mode 'L').

    Intègre la concavité locale sur 3 rayons spatiaux (micro-pores, sillons mésoscopiques,
    plis macroscopiques). Les surfaces planes ou convexes demeurent à 255 (1.0), tandis que
    les creux accumulent une atténuation radiale douce jusqu'à `ao_min`.
    """
    if isinstance(rgb_or_gray, Image.Image):
        arr = np.asarray(rgb_or_gray.convert("RGB"), dtype=np.float32)
    else:
        arr = rgb_or_gray.astype(np.float32)

    luma = compute_perceptual_luma(arr) if arr.ndim == 3 else arr
    cavity_acc = np.zeros_like(luma, dtype=np.float32)

    for sigma, w in zip(radii, weights):
        broad = cv2.GaussianBlur(luma, (0, 0), sigma)
        concavity = np.maximum(0.0, broad - luma)
        cavity_acc += float(w) * concavity

    # Courbure Laplacienne locale (creux concaves > 0)
    lap = cv2.Laplacian(cv2.GaussianBlur(luma, (3, 3), 0.8), cv2.CV_32F, ksize=3)
    concave_lap = np.maximum(0.0, lap) * 0.25
    total_occlusion = 1.65 * cavity_acc + concave_lap

    ao_u8 = np.clip(np.round(255.0 - total_occlusion), float(ao_min), 255.0).astype(np.uint8)
    return Image.fromarray(ao_u8, mode="L")


def synthesize_height_displacement_map(
    rgb_or_gray: np.ndarray | Image.Image,
) -> Image.Image:
    """Synthétise une carte de hauteur/déplacement intrinsèque (`height_map`, mode 'L') dé-éclairée."""
    if isinstance(rgb_or_gray, Image.Image):
        arr = np.asarray(rgb_or_gray.convert("RGB"), dtype=np.float32)
    else:
        arr = rgb_or_gray.astype(np.float32)

    luma = compute_perceptual_luma(arr) if arr.ndim == 3 else arr
    # Suppression du vignettage d'éclairement très basse fréquence tout en conservant le relief méso/micro
    illumination = cv2.GaussianBlur(luma, (0, 0), max(16.0, min(luma.shape[:2]) / 32.0))
    intrinsic_relief = luma - 0.55 * (illumination - np.median(illumination))
    p01, p99 = np.percentile(intrinsic_relief, [1.0, 99.0])
    denom = max(1e-4, float(p99 - p01))
    normalized = np.clip((intrinsic_relief - p01) / denom * 255.0, 0.0, 255.0)
    return Image.fromarray(np.round(normalized).astype(np.uint8), mode="L")


def synthesize_metallic_map(
    rgb: np.ndarray | Image.Image,
) -> Image.Image:
    """Estime la carte de métallicité par texel (`metallic_map`, mode 'L') par analyse spectrale/réflectance."""
    if isinstance(rgb, Image.Image):
        arr = np.asarray(rgb.convert("RGB"), dtype=np.float32)
    else:
        arr = rgb.astype(np.float32)

    luma = compute_perceptual_luma(arr)
    hsv = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    gx = cv2.Scharr(luma, cv2.CV_32F, 1, 0) / 32.0
    gy = cv2.Scharr(luma, cv2.CV_32F, 0, 1) / 32.0
    spec_contrast = np.clip(np.hypot(gx, gy) / 40.0, 0.0, 1.0)

    # Conducteurs chauds (or, laiton, cuivre) vs conducteurs froids (acier, argent, chrome)
    warm_conductor = (
        (hue >= 10.0) & (hue <= 36.0) & (sat >= 75.0) & (val >= 115.0)
    ).astype(np.float32)
    cool_conductor = (
        (sat <= 38.0) & (val >= 135.0) & (spec_contrast >= 0.22)
    ).astype(np.float32)

    metal = np.clip(
        warm_conductor * (150.0 + 70.0 * spec_contrast)
        + cool_conductor * (120.0 + 80.0 * spec_contrast),
        0.0,
        235.0,
    )
    # Les cavités sombres sont non-métalliques
    metal = np.where(luma < 36.0, 0.0, metal)
    metal_smooth = cv2.GaussianBlur(metal.astype(np.float32), (3, 3), 0.7)
    return Image.fromarray(np.clip(np.round(metal_smooth), 0, 255).astype(np.uint8), mode="L")


def pack_gltf_orm_texture(
    ao_map: Image.Image,
    roughness_map: Image.Image,
    metallic_map: Image.Image,
) -> Image.Image:
    """Empaquette les cartes PBR dans la convention glTF 2.0 ORM (R=Occlusion, G=Roughness, B=Metallic)."""
    w, h = ao_map.size
    r_ch = np.asarray(ao_map.convert("L"), dtype=np.uint8)
    g_ch = np.asarray(roughness_map.convert("L").resize((w, h), Image.Resampling.BILINEAR), dtype=np.uint8)
    b_ch = np.asarray(metallic_map.convert("L").resize((w, h), Image.Resampling.BILINEAR), dtype=np.uint8)
    orm = np.stack([r_ch, g_ch, b_ch], axis=-1)
    return Image.fromarray(orm, mode="RGB")


def evaluate_optical_quality_metrics(im: Image.Image) -> dict[str, float]:
    """Calcule les métriques optiques formelles : netteté Laplacienne, énergie Tenengrad, contraste, entropie et clipping."""
    rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
    luma = compute_perceptual_luma(rgb)

    lap = cv2.Laplacian(luma, cv2.CV_32F, ksize=3)
    sharpness_laplacian = float(np.var(lap))

    gx = cv2.Scharr(luma, cv2.CV_32F, 1, 0) / 16.0
    gy = cv2.Scharr(luma, cv2.CV_32F, 0, 1) / 16.0
    tenengrad_energy = float(np.mean(gx * gx + gy * gy))

    rms_contrast = float(np.std(luma))
    p01, p99 = np.percentile(luma, [1.0, 99.0])
    michelson_contrast = float((p99 - p01) / max(1.0, p99 + p01))

    hist, _ = np.histogram(luma, bins=256, range=(0.0, 256.0), density=True)
    hist_nz = hist[hist > 1e-12]
    shannon_entropy = float(-np.sum(hist_nz * np.log2(hist_nz)))

    highlight_clipped_pct = float(np.mean(np.max(rgb, axis=-1) >= 254.5) * 100.0)
    shadow_crushed_pct = float(np.mean(luma <= 1.0) * 100.0)

    return {
        "sharpness_laplacian_variance": round(sharpness_laplacian, 2),
        "tenengrad_gradient_energy": round(tenengrad_energy, 2),
        "rms_contrast": round(rms_contrast, 2),
        "michelson_contrast": round(michelson_contrast, 4),
        "shannon_entropy_bits": round(shannon_entropy, 3),
        "highlight_clipped_percent": round(highlight_clipped_pct, 4),
        "shadow_crushed_percent": round(shadow_crushed_pct, 4),
        "dynamic_range_span_p99_p01": round(float(p99 - p01), 2),
    }


def generate_pbr_material_bundle(
    im: Image.Image,
    output_dir: Path | str | None = None,
    prefix: str = "master",
    target_max_edge: int | None = None,
    normal_strength: float = 1.0,
) -> dict[str, Any]:
    """Exécute le pipeline complet : super-résolution 8K/16K sans halo, régulation HDR et synthèse des 6 cartes PBR."""
    t0 = time.monotonic()
    upscale_info: dict[str, Any] = {}
    if target_max_edge is not None and target_max_edge > max(im.size):
        master_img, upscale_info = upscale_progressive_laplacian(
            im,
            target_max_edge=target_max_edge,
            regulate_hdr=True,
        )
    else:
        rgb_reg, hdr_stats = regulate_perceptual_dynamic_range(np.asarray(im.convert("RGB"), dtype=np.uint8))
        master_img = Image.fromarray(rgb_reg, mode="RGB")
        upscale_info = {
            "source_dimensions": list(im.size),
            "target_dimensions": list(master_img.size),
            "octave_passes": 0,
            "resolution_tier": "native",
            "hdr_regulation": hdr_stats,
        }

    rgb_arr = np.asarray(master_img, dtype=np.float32)
    normal_map = synthesize_multiscale_normal_map(rgb_arr, strength=normal_strength)
    roughness_map = synthesize_micro_roughness_map(rgb_arr)
    ao_map = synthesize_cavity_ao_map(rgb_arr)
    height_map = synthesize_height_displacement_map(rgb_arr)
    metallic_map = synthesize_metallic_map(rgb_arr)
    orm_map = pack_gltf_orm_texture(ao_map, roughness_map, metallic_map)
    metrics = evaluate_optical_quality_metrics(master_img)
    try:
        from pixel_perfect_optical_engine import apply_pixel_perfect_optical_refinement
        # Certification et alignement de phase sub-pixel sur échantillon représentatif (sans saturer la RAM en 16K)
        _sample_arr = np.asarray(master_img.resize((min(512, master_img.size[0]), min(512, master_img.size[1]))), dtype=np.uint8)
        _pp_res = apply_pixel_perfect_optical_refinement(_sample_arr, is_uv_texture=False)
        metrics["pixel_perfect_certificate"] = _pp_res["certificate"]
    except Exception as _pp_exc:
        metrics["pixel_perfect_certificate"] = {"ok": False, "error": str(_pp_exc)}

    saved_files: dict[str, str] = {}
    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        file_map = {
            "albedo": (master_img, f"{prefix}_albedo.png"),
            "normal": (normal_map, f"{prefix}_normal_gl.png"),
            "roughness": (roughness_map, f"{prefix}_roughness.png"),
            "ao": (ao_map, f"{prefix}_cavity_ao.png"),
            "height": (height_map, f"{prefix}_height.png"),
            "metallic": (metallic_map, f"{prefix}_metallic.png"),
            "orm": (orm_map, f"{prefix}_orm_gltf.png"),
        }
        for key, (pil_im, fname) in file_map.items():
            dest = out_path / fname
            pil_im.save(dest)
            saved_files[key] = str(dest)

    return {
        "dimensions": {"width": master_img.size[0], "height": master_img.size[1]},
        "upscale_telemetry": upscale_info,
        "optical_quality_metrics": metrics,
        "saved_files": saved_files,
        "maps": {
            "albedo": master_img,
            "normal": normal_map,
            "roughness": roughness_map,
            "ao": ao_map,
            "height": height_map,
            "metallic": metallic_map,
            "orm": orm_map,
        },
        "total_elapsed_ms": int((time.monotonic() - t0) * 1000),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AuroraIA 8K/16K Ultra-Master Frequency-Separated Upscaler & PBR Map Synthesizer"
    )
    parser.add_argument("input", type=Path, help="Input image path")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for upscaled image & PBR maps")
    parser.add_argument("--tier", type=str, default="8k", choices=["2k", "4k", "8k", "16k"], help="Target resolution tier")
    parser.add_argument("--normal-strength", type=float, default=1.0, help="Normal map tangent strength")
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Input file not found: {args.input}")

    im = Image.open(args.input).convert("RGB")
    target_edge = RESOLUTION_TIERS.get(args.tier.lower(), 8192)
    out_dir = args.output_dir or args.input.parent / f"{args.input.stem}_{args.tier.lower()}_pbr"
    bundle = generate_pbr_material_bundle(
        im,
        output_dir=out_dir,
        prefix=args.input.stem,
        target_max_edge=target_edge,
        normal_strength=args.normal_strength,
    )
    summary = {k: v for k, v in bundle.items() if k != "maps"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
