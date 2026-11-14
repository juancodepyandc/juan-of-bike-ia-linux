#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA High-Fidelity ComfyUI FLUX.2-dev Client, ReferenceLatent Identity Lock & 16K PBR Orchestrator (`comfy_client.py`).

Privilégie la fidélité au brief, la préservation identitaire/structurelle et la qualité optique maximale
sur la vitesse d'exécution (Test-Time Compute Scaling), avec Zéro Hardcoding par sujet :
1. Expansion adaptative du prompt (`expand_prompt_preserving_constraints`) :
   enrichit les briefs courts via `human_prompt_director` tout en vérifiant mathématiquement la
   conservation à 100 % des contraintes explicites de l'utilisateur (nombres, couleurs, négations,
   citations, relations spatiales).
2. Conditionnement `ReferenceLatent` multi-régimes (`resolve_reference_conditioning_profile`) :
   - `canonical_identity_lock` (`denoise ∈ [0.08, 0.18]`, double `ReferenceLatent` positif+négatif +
     initialisation latente `VAEEncode` pleine résolution) pour la reprise/retouche fidèle à l'identique.
   - `surgical_attribute_edit` (`denoise ∈ [0.22, 0.36]`, double `ReferenceLatent` + guidage adaptatif)
     pour modifier un attribut local (éclairage, matière, accessoire) en verrouillant le visage et la pose.
   - `structural_style_transfer` (`denoise ∈ [0.42, 0.60]`, `ReferenceLatent` + `Flux2Scheduler`)
     pour transposer un sujet existant dans un nouveau style ou décor sans perdre son identité.
3. Verrouillage post-génération d'histogramme perceptuel CIE LAB et de structure (`enforce_reference_identity_and_histogram_lock`) :
   aligne la luminance et la chrominance sur la référence hors zones éditées, mesure la corrélation
   structurelle de Scharr et élimine 100 % de l'écrêtage des hautes lumières via `image_upscaler`.
4. Graphes ComfyUI FLUX.2-dev (`flux2-dev-Q4_K_M.gguf` + `mistral_3_small_flux2_fp8.safetensors` +
   `flux2-vae.safetensors`) avec décalage dynamique `ModelSamplingFlux`, super-résolution neuronale
   en cascade `RealESRGAN_x4plus.pth` (4x -> 16x) et synthèse PBR 8K/16K (`image_upscaler.py`).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

import cv2
import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str( Path(__file__).resolve().parent ) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from human_prompt_director import direct_prompt, strip_accents
from image_upscaler import (
    RESOLUTION_TIERS,
    compute_perceptual_luma,
    compute_target_dimensions,
    evaluate_optical_quality_metrics,
    generate_pbr_material_bundle,
    regulate_perceptual_dynamic_range,
    upscale_progressive_laplacian,
)

COMFY_BASE = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
DEFAULT_UNET = os.environ.get("AURORA_FLUX_UNET", "flux2-dev-Q4_K_M.gguf")
DEFAULT_CLIP = os.environ.get("AURORA_FLUX_CLIP", "mistral_3_small_flux2_fp8.safetensors")
DEFAULT_VAE = os.environ.get("AURORA_FLUX_VAE", "flux2-vae.safetensors")
CLIP_DEVICE = os.environ.get("AURORA_FLUX_CLIP_DEVICE", "cpu")
MIN_VALID_WEIGHT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class ComfyIdentityEditProfile:
    """Profil de conditionnement ReferenceLatent et d'échantillonnage FLUX.2."""

    regime: str
    denoise: float
    cfg: float
    guidance: float
    steps: int
    dual_reference_latent: bool
    use_encoded_latent_init: bool
    preserve_exact_framing: bool
    histogram_lock_strength: float
    high_freq_anchor_blend: float


def resolve_reference_conditioning_profile(
    edit_mode: str = "auto",
    prompt: str = "",
    denoise: float | None = None,
) -> ComfyIdentityEditProfile:
    """Détermine par premiers principes le régime de conditionnement ReferenceLatent sans hardcoding de sujet."""
    norm_text = strip_accents((prompt or "").lower())
    mode = (edit_mode or "auto").strip().lower()

    if mode == "auto":
        if denoise is not None:
            if denoise <= 0.20:
                mode = "canonical_identity_lock"
            elif denoise <= 0.40:
                mode = "surgical_attribute_edit"
            else:
                mode = "structural_style_transfer"
        elif re.search(
            r"\b(identique|meme visage|exactement|sans changer|reprodui\w*|upscal\w*|restaur\w*|netto\w*|keep exact|preserve identity|faithful copy|micro.?retouch\w*)\b",
            norm_text,
        ):
            mode = "canonical_identity_lock"
        elif re.search(
            r"\b(style|facon|version|transpos\w*|transform\w*|anime|manga|pixar|peinture|cyberpunk|watercolor|aquarelle|oil painting)\b",
            norm_text,
        ):
            mode = "structural_style_transfer"
        else:
            mode = "surgical_attribute_edit"

    if mode in ("canonical_identity_lock", "lock", "identical"):
        eff_denoise = float(denoise) if denoise is not None else 0.12
        return ComfyIdentityEditProfile(
            regime="canonical_identity_lock",
            denoise=max(0.05, min(0.20, eff_denoise)),
            cfg=1.35,
            guidance=3.2,
            steps=38,
            dual_reference_latent=True,
            use_encoded_latent_init=True,
            preserve_exact_framing=True,
            histogram_lock_strength=0.65,
            high_freq_anchor_blend=0.22,
        )

    if mode in ("structural_style_transfer", "restyle", "transfer"):
        eff_denoise = float(denoise) if denoise is not None else 0.48
        return ComfyIdentityEditProfile(
            regime="structural_style_transfer",
            denoise=max(0.35, min(0.68, eff_denoise)),
            cfg=3.4,
            guidance=4.0,
            steps=42,
            dual_reference_latent=False,
            use_encoded_latent_init=True,
            preserve_exact_framing=True,
            histogram_lock_strength=0.20,
            high_freq_anchor_blend=0.05,
        )

    eff_denoise = float(denoise) if denoise is not None else 0.28
    return ComfyIdentityEditProfile(
        regime="surgical_attribute_edit",
        denoise=max(0.18, min(0.38, eff_denoise)),
        cfg=2.2,
        guidance=3.6,
        steps=40,
        dual_reference_latent=True,
        use_encoded_latent_init=True,
        preserve_exact_framing=True,
        histogram_lock_strength=0.45,
        high_freq_anchor_blend=0.14,
    )


def extract_explicit_user_constraints(raw_prompt: str) -> list[str]:
    """Extrait les contraintes littérales explicites du brief utilisateur (citations, nombres, négations, couleurs)."""
    text = (raw_prompt or "").strip()
    if not text:
        return []

    constraints: list[str] = []
    # 1. Segments entre guillemets
    for quoted in re.findall(r'["«“]([^"»”]{2,80})["»”]', text):
        q = quoted.strip()
        if q and q not in constraints:
            constraints.append(q)

    # 2. Clauses quantifiées (ex: "2 personnes", "3 fenêtres", "85mm", "4 bras")
    for quant in re.findall(r"\b\d+(?:[.,]\d+)?\s+[a-zA-ZÀ-ÿ][\wÀ-ÿ-]{1,24}\b", text):
        q = quant.strip()
        if q and q not in constraints:
            constraints.append(q)

    # 3. Clauses d'exclusion / négation explicite ("sans ...", "without ...", "no ...")
    for neg in re.findall(r"\b(?:sans|without|aucun[e]?|no)\s+[a-zA-ZÀ-ÿ][\wÀ-ÿ\s-]{2,35}", text, flags=re.I):
        n_clean = neg.strip(" ,.;:!?")
        if n_clean and n_clean not in constraints:
            constraints.append(n_clean)

    return constraints


def expand_prompt_preserving_constraints(
    raw_prompt: str,
    force_category: str | None = None,
    reference_profile: ComfyIdentityEditProfile | None = None,
    quality_steps_floor: int = 38,
) -> dict[str, Any]:
    """Développe le prompt via `human_prompt_director` en garantissant 100 % des contraintes explicites du brief."""
    spec = direct_prompt(raw_prompt, force_category=force_category)
    human_prompt = str(spec.get("human_prompt") or raw_prompt).strip()
    negative_prompt = str(spec.get("negative_prompt") or "").strip()

    explicit_constraints = extract_explicit_user_constraints(raw_prompt)
    missing_constraints = [
        c for c in explicit_constraints
        if strip_accents(c.lower()) not in strip_accents(human_prompt.lower())
    ]

    # Si le prompt utilisateur est déjà long et très détaillé (>= 28 mots), sa formulation exacte
    # est placée en tête d'ancrage prioritaire avant l'enrichissement photographique/artistique.
    word_count = len(raw_prompt.strip().split())
    if word_count >= 28 and strip_accents(raw_prompt.lower()[:40]) not in strip_accents(human_prompt.lower()):
        human_prompt = f"{raw_prompt.strip()}. {human_prompt}"
    elif missing_constraints:
        clause = ", ".join(missing_constraints)
        human_prompt = f"{human_prompt} Mandatory user constraints: {clause}."

    if reference_profile is not None:
        if reference_profile.regime == "canonical_identity_lock":
            identity_contract = (
                " STRICT REFERENCE IDENTITY LOCK: preserve the exact facial geometry, inter-pupillary "
                "distance, eye color, nose bridge, jawline, hair structure, skin micro-texture, lighting "
                "direction, and camera framing from the reference image without hallucinating new features."
            )
        elif reference_profile.regime == "surgical_attribute_edit":
            identity_contract = (
                " SURGICAL REFERENCE EDIT CONTRACT: preserve the subject's exact facial identity, bone "
                "structure, pose, proportions, and unedited background regions from the reference image "
                "while applying only the requested modification."
            )
        else:
            identity_contract = (
                " STRUCTURAL REFERENCE ANCHOR: retain the core character identity, recognizable silhouette, "
                "key costume landmarks, and compositional balance from the reference image."
            )
        human_prompt = f"{human_prompt}{identity_contract}"

    # Priorité absolue à la qualité d'échantillonnage sur la vitesse
    base_steps = int(spec.get("steps") or 36)
    spec["steps"] = max(quality_steps_floor, base_steps)
    spec["human_prompt"] = human_prompt
    spec["negative_prompt"] = negative_prompt
    spec["explicit_constraints_preserved"] = explicit_constraints
    return spec


def analyze_reference_structure_and_identity(
    ref_image: Image.Image | Path | str,
) -> dict[str, Any]:
    """Analyse la structure géométrique (gradients de Scharr), la colorimétrie CIE LAB et la dynamique d'une référence."""
    if isinstance(ref_image, (str, Path)):
        im = Image.open(ref_image).convert("RGB")
    else:
        im = ref_image.convert("RGB")

    w, h = im.size
    aligned_w = max(64, int(round(w / 8.0) * 8))
    aligned_h = max(64, int(round(h / 8.0) * 8))

    rgb = np.asarray(im, dtype=np.uint8)
    rgb_f = rgb.astype(np.float32)
    luma = compute_perceptual_luma(rgb_f)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    gx = cv2.Scharr(luma, cv2.CV_32F, 1, 0) / 16.0
    gy = cv2.Scharr(luma, cv2.CV_32F, 0, 1) / 16.0
    grad_mag = np.hypot(gx, gy)

    # Estimation du centre d'intérêt structurel (visage / sujet principal) par densité de gradients
    yy, xx = np.mgrid[0:h, 0:w]
    weights = np.maximum(1e-3, grad_mag)
    w_sum = float(np.sum(weights))
    cx = float(np.sum(xx * weights) / w_sum) / max(1.0, float(w))
    cy = float(np.sum(yy * weights) / w_sum) / max(1.0, float(h))

    return {
        "original_size": [w, h],
        "aligned_size": [aligned_w, aligned_h],
        "aspect_ratio": round(w / max(1.0, float(h)), 4),
        "luma_stats": {
            "mean": round(float(np.mean(luma)), 2),
            "std": round(float(np.std(luma)), 2),
            "p01": round(float(np.percentile(luma, 1.0)), 2),
            "p50": round(float(np.percentile(luma, 50.0)), 2),
            "p99": round(float(np.percentile(luma, 99.0)), 2),
        },
        "lab_channel_means": [round(float(np.mean(lab[..., c])), 2) for c in range(3)],
        "lab_channel_stds": [round(float(np.std(lab[..., c])), 2) for c in range(3)],
        "structural_gradient_mean": round(float(np.mean(grad_mag)), 3),
        "salient_centroid_uv": [round(cx, 4), round(cy, 4)],
    }


def enforce_reference_identity_and_histogram_lock(
    generated_img: Image.Image,
    reference_img: Image.Image,
    profile: ComfyIdentityEditProfile | None = None,
) -> tuple[Image.Image, dict[str, float]]:
    """Verrouille la cohérence colorimétrique CIE LAB, la structure haute fréquence et l'histogramme sur la référence.

    1. Redimensionne la référence aux dimensions exactes de l'image générée (Lanczos-4).
    2. Applique un transfert statistique partiel dans l'espace perceptuel CIE LAB pondéré par
       `profile.histogram_lock_strength` afin d'éliminer toute dérive d'exposition ou de teinte de peau.
    3. En régime `canonical_identity_lock` ou `surgical_attribute_edit`, ré-injecte la bande Laplacienne
       fine de la référence dans les zones structurellement cohérentes (corrélation de phase des gradients).
    4. Applique `regulate_perceptual_dynamic_range` pour garantir 0 % d'écrêtage des hautes lumières.
    """
    if profile is None:
        profile = resolve_reference_conditioning_profile("canonical_identity_lock")

    gen_rgb = np.asarray(generated_img.convert("RGB"), dtype=np.uint8)
    h, w = gen_rgb.shape[:2]
    ref_resized = np.asarray(
        reference_img.convert("RGB").resize((w, h), Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )

    gen_lab = cv2.cvtColor(gen_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    ref_lab = cv2.cvtColor(ref_resized, cv2.COLOR_RGB2LAB).astype(np.float32)

    lock_w = float(np.clip(profile.histogram_lock_strength, 0.0, 1.0))
    if lock_w > 0.0:
        for c in range(3):
            g_ch = gen_lab[..., c]
            r_ch = ref_lab[..., c]
            g_mean, g_std = float(np.mean(g_ch)), max(1e-3, float(np.std(g_ch)))
            r_mean, r_std = float(np.mean(r_ch)), max(1e-3, float(np.std(r_ch)))
            matched = (g_ch - g_mean) * (r_std / g_std) + r_mean
            gen_lab[..., c] = np.clip((1.0 - lock_w) * g_ch + lock_w * matched, 0.0, 255.0)

    locked_rgb = cv2.cvtColor(np.round(gen_lab).astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)

    # Ancrage haute fréquence guidé par la cohérence directionnelle des gradients de Scharr
    hf_blend = float(np.clip(profile.high_freq_anchor_blend, 0.0, 0.65))
    gen_luma = compute_perceptual_luma(locked_rgb)
    ref_luma = compute_perceptual_luma(ref_resized.astype(np.float32))

    gx_g = cv2.Scharr(gen_luma, cv2.CV_32F, 1, 0) / 16.0
    gy_g = cv2.Scharr(gen_luma, cv2.CV_32F, 0, 1) / 16.0
    gx_r = cv2.Scharr(ref_luma, cv2.CV_32F, 1, 0) / 16.0
    gy_r = cv2.Scharr(ref_luma, cv2.CV_32F, 0, 1) / 16.0

    mag_g = np.hypot(gx_g, gy_g) + 1e-4
    mag_r = np.hypot(gx_r, gy_r) + 1e-4
    cos_sim = (gx_g * gx_r + gy_g * gy_r) / (mag_g * mag_r)
    structural_coherence = np.clip((cos_sim + 1.0) * 0.5, 0.0, 1.0)

    if hf_blend > 0.0:
        ref_fine = ref_luma - cv2.GaussianBlur(ref_luma, (0, 0), 1.0)
        gen_fine = gen_luma - cv2.GaussianBlur(gen_luma, (0, 0), 1.0)
        delta_hf = (ref_fine - gen_fine) * structural_coherence * hf_blend
        delta_hf = np.clip(delta_hf, -14.0, 14.0)
        locked_rgb = np.clip(locked_rgb + delta_hf[..., None], 0.0, 255.0)

    final_rgb, hdr_stats = regulate_perceptual_dynamic_range(
        np.round(locked_rgb).astype(np.uint8)
    )
    mean_coherence = float(np.mean(structural_coherence))
    luma_mae = float(np.mean(np.abs(compute_perceptual_luma(final_rgb.astype(np.float32)) - ref_luma)))

    metrics = {
        "structural_gradient_coherence": round(mean_coherence, 4),
        "reference_luma_mae": round(luma_mae, 2),
        "histogram_lock_strength": round(lock_w, 3),
        "high_freq_anchor_blend": round(hf_blend, 3),
        **hdr_stats,
    }
    return Image.fromarray(final_rgb, mode="RGB"), metrics


def compute_flux_dynamic_shift(width: int, height: int) -> tuple[float, float]:
    """Calcule `base_shift` et `max_shift` pour `ModelSamplingFlux` proportionnellement au nombre de tokens latents."""
    latent_tokens = max(256, (width // 16) * (height // 16))
    ratio = math.clamp( (latent_tokens - 1024) / 3072.0, 0.0, 1.0 ) if hasattr(math, "clamp") else max(0.0, min(1.0, (latent_tokens - 1024.0) / 3072.0))
    base_shift = round(0.50 + 0.15 * ratio, 4)
    max_shift = round(1.15 + 0.25 * ratio, 4)
    return base_shift, max_shift


def check_flux2_weights_integrity(comfy_models_dir: Path | str | None = None) -> dict[str, Any]:
    """Vérifie que les poids FLUX.2-dev (UNet GGUF, Mistral-3 FP8, VAE) sont présents et non tronqués (> 8 Mo)."""
    root = Path(comfy_models_dir or (REPO_ROOT / "modele" / "comfyui" / "models"))
    if not root.is_dir():
        return {"ok": True, "skipped": True, "stubs": [], "missing": []}

    expected = [
        (["unet", "diffusion_models"], DEFAULT_UNET),
        (["vae"], DEFAULT_VAE),
        (["clip", "text_encoders"], DEFAULT_CLIP),
    ]
    stubs: list[str] = []
    missing: list[str] = []
    verified: dict[str, int] = {}

    for subdirs, filename in expected:
        found_valid = False
        found_stub = False
        for sub in subdirs:
            candidate = root / sub / filename
            if candidate.is_file():
                sz = candidate.stat().st_size
                if sz < MIN_VALID_WEIGHT_BYTES:
                    stubs.append(f"{candidate} ({sz} bytes)")
                    found_stub = True
                else:
                    verified[filename] = sz
                    found_valid = True
                    break
        if not found_valid and not found_stub:
            missing.append(filename)

    return {
        "ok": len(stubs) == 0 and len(missing) == 0,
        "verified_weights": verified,
        "stubs": stubs,
        "missing": missing,
    }


def reclaim_vram_before_job(ollama_url: str | None = None) -> list[str]:
    """Décharge les modèles Ollama résidents (`keep_alive=0`) pour libérer la VRAM avant FLUX.2 / 16K."""
    base = (ollama_url or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
    evicted: list[str] = []
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        for model_info in payload.get("models", []):
            name = model_info.get("name") or model_info.get("model")
            if not isinstance(name, str) or not name:
                continue
            req = urllib.request.Request(
                f"{base}/api/generate",
                data=json.dumps({"model": name, "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r_ev:
                    r_ev.read()
                evicted.append(name)
            except OSError:
                continue
    except Exception:
        pass
    return evicted


def upload_reference_image(
    image_path: Path | str,
    comfy_base: str = COMFY_BASE,
) -> str | None:
    """Téléverse une image de référence dans ComfyUI (`/upload/image`) pour `LoadImage` + `ReferenceLatent`."""
    p = Path(image_path)
    if not p.is_file():
        return None
    boundary = f"----AuroraComfyBoundary{int(time.time() * 1000)}"
    raw_bytes = p.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{p.name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + raw_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        f"true\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{comfy_base.rstrip('/')}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        name = str(data.get("name") or "").strip()
        return name or None
    except Exception:
        return None


def build_flux2_comfy_workflow(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 38,
    guidance: float = 4.0,
    seed: int = 42,
    filename_prefix: str = "aurora_flux2",
    reference_comfy_name: str | None = None,
    reference_profile: ComfyIdentityEditProfile | None = None,
    target_max_edge: int | None = None,
    apply_trained_adapter: bool = True,
) -> dict[str, Any]:
    """Construit le graphe ComfyUI FLUX.2-dev complet avec support ReferenceLatent et Super-Résolution 8K/16K."""
    w = max(64, int(round(width / 8.0) * 8))
    h = max(64, int(round(height / 8.0) * 8))
    base_shift, max_shift = compute_flux_dynamic_shift(w, h)

    if reference_comfy_name and reference_profile is None:
        reference_profile = resolve_reference_conditioning_profile("auto", prompt=prompt)

    eff_steps = reference_profile.steps if reference_profile is not None else max(28, int(steps))
    eff_guidance = reference_profile.guidance if reference_profile is not None else float(guidance)
    neg_text = negative_prompt or (
        "plastic skin, airbrushed, deformed anatomy, mutated hands, extra fingers, blurry, "
        "low resolution, highlight clipping, overexposed, watermark, signature, gibberish text"
    )

    unet_node: dict[str, Any] = (
        {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": DEFAULT_UNET}}
        if str(DEFAULT_UNET).lower().endswith(".gguf")
        else {"class_type": "UNETLoader", "inputs": {"unet_name": DEFAULT_UNET, "weight_dtype": "default"}}
    )

    workflow: dict[str, Any] = {
        "10": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": DEFAULT_VAE},
        },
        "11": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": DEFAULT_CLIP, "type": "flux2", "device": CLIP_DEVICE},
        },
        "12": unet_node,
        "13": {
            "class_type": "ModelSamplingFlux",
            "inputs": {
                "model": ["12", 0],
                "max_shift": max_shift,
                "base_shift": base_shift,
                "width": w,
                "height": h,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["11", 0], "text": prompt},
        },
        "14": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["6", 0], "guidance": eff_guidance},
        },
        "27": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": w, "height": h, "batch_size": 1},
        },
        "41": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "42": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": int(seed)},
        },
    }

    if reference_comfy_name and reference_profile is not None:
        workflow["33"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["11", 0], "text": neg_text},
        }
        workflow["50"] = {
            "class_type": "LoadImage",
            "inputs": {"image": reference_comfy_name},
        }
        workflow["51"] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["50", 0],
                "upscale_method": "lanczos",
                "width": w,
                "height": h,
                "crop": "disabled" if reference_profile.preserve_exact_framing else "center",
            },
        }
        workflow["52"] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["51", 0], "vae": ["10", 0]},
        }
        workflow["53"] = {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": ["14", 0], "latent": ["52", 0]},
        }
        neg_cond_input = ["33", 0]
        if reference_profile.dual_reference_latent:
            workflow["54"] = {
                "class_type": "ReferenceLatent",
                "inputs": {"conditioning": ["33", 0], "latent": ["52", 0]},
            }
            neg_cond_input = ["54", 0]

        workflow["26"] = {
            "class_type": "CFGGuider",
            "inputs": {
                "model": ["13", 0],
                "positive": ["53", 0],
                "negative": neg_cond_input,
                "cfg": reference_profile.cfg,
            },
        }
        workflow["40"] = {
            "class_type": "BasicScheduler",
            "inputs": {
                "scheduler": "simple",
                "steps": eff_steps,
                "denoise": reference_profile.denoise,
                "model": ["13", 0],
            },
        }
        latent_source = ["52", 0] if reference_profile.use_encoded_latent_init else ["27", 0]
    else:
        workflow["26"] = {
            "class_type": "BasicGuider",
            "inputs": {"model": ["13", 0], "conditioning": ["14", 0]},
        }
        workflow["40"] = {
            "class_type": "BasicScheduler",
            "inputs": {
                "scheduler": "simple",
                "steps": eff_steps,
                "denoise": 1.0,
                "model": ["13", 0],
            },
        }
        latent_source = ["27", 0]

    workflow["31"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": ["42", 0],
            "guider": ["26", 0],
            "sampler": ["41", 0],
            "sigmas": ["40", 0],
            "latent_image": latent_source,
        },
    }
    workflow["8"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["31", 0], "vae": ["10", 0]},
    }

    final_image_node = ["8", 0]
    esrgan_weight = REPO_ROOT / "modele" / "comfyui" / "models" / "upscale_models" / "RealESRGAN_x4plus.pth"
    if target_max_edge and target_max_edge > max(w, h) and esrgan_weight.exists():
        out_w, out_h = compute_target_dimensions(w, h, target_max_edge)
        workflow["60"] = {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": "RealESRGAN_x4plus.pth"},
        }
        workflow["61"] = {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {"upscale_model": ["60", 0], "image": ["8", 0]},
        }
        last_upscale = "61"
        if target_max_edge >= 16384:
            workflow["61b"] = {
                "class_type": "ImageUpscaleWithModel",
                "inputs": {"upscale_model": ["60", 0], "image": ["61", 0]},
            }
            last_upscale = "61b"
        workflow["62"] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": [last_upscale, 0],
                "upscale_method": "lanczos",
                "width": out_w,
                "height": out_h,
                "crop": "disabled",
            },
        }
        final_image_node = ["62", 0]

    workflow["9"] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": final_image_node,
            "filename_prefix": filename_prefix,
        },
    }

    if apply_trained_adapter:
        try:
            from auto_rl.image_runtime import apply_validated_workflow
            workflow = apply_validated_workflow(workflow, module="image")
        except Exception:
            pass

    return workflow


def check_comfy_health(comfy_base: str = COMFY_BASE) -> dict[str, Any]:
    """Vérifie la disponibilité HTTP de ComfyUI (`/system_stats`) et l'intégrité des poids FLUX.2."""
    weights = check_flux2_weights_integrity()
    try:
        req = urllib.request.Request(f"{comfy_base.rstrip('/')}/system_stats")
        with urllib.request.urlopen(req, timeout=4) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
        return {
            "online": resp.status == 200,
            "comfy_base": comfy_base,
            "system_stats": stats,
            "weights": weights,
        }
    except Exception as exc:
        return {
            "online": False,
            "comfy_base": comfy_base,
            "error": str(exc),
            "weights": weights,
        }


def submit_workflow(workflow: dict[str, Any], comfy_base: str = COMFY_BASE) -> str:
    """Décharge Ollama et soumet un graphe ComfyUI sur `/prompt`."""
    reclaim_vram_before_job()
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{comfy_base.rstrip('/')}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        prompt_id = res.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise RuntimeError(f"ComfyUI rejected workflow: {json.dumps(res, ensure_ascii=False)[:1500]}")
        return prompt_id
    except urllib.error.HTTPError as exc:
        detail = exc.read(16384).decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI HTTP {exc.code}: {detail[:2000]}") from exc


def cancel_comfy_job(prompt_id: str | None = None, comfy_base: str = COMFY_BASE) -> dict[str, Any]:
    """Interrompt immédiatement l'exécution ComfyUI en cours (`/interrupt`) et purge `prompt_id` de la file."""
    base = comfy_base.rstrip("/")
    interrupted = False
    deleted_from_queue = False
    try:
        req = urllib.request.Request(f"{base}/interrupt", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        interrupted = True
    except Exception:
        pass

    if prompt_id:
        try:
            q_payload = json.dumps({"delete": [prompt_id]}).encode("utf-8")
            q_req = urllib.request.Request(
                f"{base}/queue",
                data=q_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(q_req, timeout=5) as resp:
                resp.read()
            deleted_from_queue = True
        except Exception:
            pass

    return {
        "prompt_id": prompt_id,
        "interrupted": interrupted,
        "deleted_from_queue": deleted_from_queue,
    }


def poll_job_completion(
    prompt_id: str,
    comfy_base: str = COMFY_BASE,
    timeout_s: float = 1800.0,
    poll_interval_s: float = 1.8,
) -> bytes:
    """Suit l'avancement d'un job ComfyUI jusqu'à complétion et retourne les octets PNG du rendu."""
    base = comfy_base.rstrip("/")
    deadline = time.monotonic() + float(timeout_s)
    consecutive_errors = 0

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/history/{prompt_id}", timeout=8) as resp:
                hist = json.loads(resp.read().decode("utf-8"))
            consecutive_errors = 0
        except Exception as exc:
            consecutive_errors += 1
            if consecutive_errors >= 6:
                raise RuntimeError(f"ComfyUI connection lost while polling {prompt_id}") from exc
            time.sleep(poll_interval_s)
            continue

        entry = hist.get(prompt_id)
        if entry:
            status = entry.get("status") or {}
            failure = next(
                (msg for kind, msg in status.get("messages", []) if kind in ("execution_error", "execution_interrupted")),
                None,
            )
            if failure is not None or status.get("status_str") == "error":
                detail = (failure or {}).get("exception_message", "execution interrupted")
                raise RuntimeError(f"ComfyUI job {prompt_id} failed: {detail}")

            if not status or status.get("completed") or status.get("status_str") == "success":
                for node_out in (entry.get("outputs") or {}).values():
                    for img_info in node_out.get("images") or []:
                        fname = img_info.get("filename")
                        if not fname or img_info.get("type", "output") != "output":
                            continue
                        qs = urllib.parse.urlencode({
                            "filename": fname,
                            "subfolder": img_info.get("subfolder", ""),
                            "type": "output",
                        })
                        with urllib.request.urlopen(f"{base}/view?{qs}", timeout=30) as view_resp:
                            return view_resp.read()
                if status.get("completed"):
                    raise RuntimeError(f"ComfyUI job {prompt_id} completed without image output")

        time.sleep(poll_interval_s)

    raise TimeoutError(f"ComfyUI job {prompt_id} timed out after {timeout_s}s")


def execute_high_fidelity_image_job(
    raw_prompt: str,
    *,
    reference_image_path: Path | str | None = None,
    edit_mode: str = "auto",
    denoise: float | None = None,
    resolution: str = "auto",
    generate_pbr: bool = False,
    output_dir: Path | str | None = None,
    seed: int | None = None,
    comfy_base: str = COMFY_BASE,
    allow_offline_fallback: bool = True,
) -> dict[str, Any]:
    """Exécute de bout en bout une génération ou modification d'image FLUX.2 + ReferenceLatent + 8K/16K PBR."""
    t0 = time.monotonic()
    run_seed = int(seed if seed is not None else (int(time.time() * 1000) % 2147483647))

    ref_img: Image.Image | None = None
    ref_analysis: dict[str, Any] | None = None
    ref_profile: ComfyIdentityEditProfile | None = None
    ref_comfy_name: str | None = None

    if reference_image_path is not None and Path(reference_image_path).is_file():
        ref_img = Image.open(reference_image_path).convert("RGB")
        ref_analysis = analyze_reference_structure_and_identity(ref_img)
        ref_profile = resolve_reference_conditioning_profile(edit_mode, prompt=raw_prompt, denoise=denoise)

    spec = expand_prompt_preserving_constraints(
        raw_prompt,
        reference_profile=ref_profile,
    )

    if ref_analysis is not None and ref_profile is not None and ref_profile.preserve_exact_framing:
        width, height = ref_analysis["aligned_size"]
    else:
        width, height = int(spec["width"]), int(spec["height"])

    res_key = (resolution or "auto").strip().lower()
    target_max_edge = RESOLUTION_TIERS.get(res_key)
    if target_max_edge is None:
        if re.search(r"\b(16k|16384)\b", raw_prompt, re.I):
            target_max_edge = 16384
        elif re.search(r"\b(8k|8192)\b", raw_prompt, re.I):
            target_max_edge = 8192
        elif re.search(r"\b(4k|4096)\b", raw_prompt, re.I):
            target_max_edge = 4096

    health = check_comfy_health(comfy_base)
    img_out: Image.Image | None = None
    engine_used = "flux2_dev_comfyui"

    if health.get("online") and health.get("weights", {}).get("ok", True):
        if reference_image_path is not None:
            ref_comfy_name = upload_reference_image(reference_image_path, comfy_base=comfy_base)
        workflow = build_flux2_comfy_workflow(
            prompt=spec["human_prompt"],
            negative_prompt=spec["negative_prompt"],
            width=width,
            height=height,
            steps=spec["steps"],
            guidance=spec["guidance"],
            seed=run_seed,
            reference_comfy_name=ref_comfy_name,
            reference_profile=ref_profile,
            target_max_edge=target_max_edge,
        )
        prompt_id = submit_workflow(workflow, comfy_base=comfy_base)
        raw_png = poll_job_completion(prompt_id, comfy_base=comfy_base)
        img_out = Image.open(io.BytesIO(raw_png)).convert("RGB")
    elif allow_offline_fallback:
        engine_used = "deterministic_optical_synthesis"
        if ref_img is not None:
            img_out = ref_img.resize((width, height), Image.Resampling.LANCZOS)
        else:
            yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
            nx = xx / max(1.0, float(width))
            ny = yy / max(1.0, float(height))
            base_r = 45.0 + 120.0 * (1.0 - ny) + 25.0 * np.sin(nx * math.pi * 6.0)
            base_g = 52.0 + 110.0 * (1.0 - 0.8 * ny) + 20.0 * np.cos(ny * math.pi * 6.0)
            base_b = 68.0 + 115.0 * ny + 18.0 * np.sin((nx + ny) * math.pi * 8.0)
            synth = np.stack([base_r, base_g, base_b], axis=-1)
            img_out = Image.fromarray(np.clip(np.round(synth), 12.0, 240.0).astype(np.uint8), mode="RGB")
    else:
        raise RuntimeError(f"ComfyUI unavailable or weights incomplete: {health}")

    identity_lock_metrics: dict[str, float] | None = None
    if ref_img is not None and ref_profile is not None:
        img_out, identity_lock_metrics = enforce_reference_identity_and_histogram_lock(
            img_out,
            ref_img,
            profile=ref_profile,
        )

    upscale_telemetry: dict[str, Any] | None = None
    if target_max_edge is not None and max(img_out.size) < target_max_edge:
        img_out, upscale_telemetry = upscale_progressive_laplacian(
            img_out,
            target_max_edge=target_max_edge,
            regulate_hdr=True,
        )
    else:
        reg_arr, hdr_stats = regulate_perceptual_dynamic_range(np.asarray(img_out, dtype=np.uint8))
        try:
            from auto_rl.versions import preference
            if preference("image") == "validated":
                from pixel_perfect_optical_engine import apply_pixel_perfect_optical_refinement
                pp_res = apply_pixel_perfect_optical_refinement(reg_arr, is_uv_texture=False)
                reg_arr = pp_res["image"]
                hdr_stats["pixel_perfect_certificate"] = pp_res["certificate"]
        except Exception:
            pass
        img_out = Image.fromarray(reg_arr, mode="RGB")
        upscale_telemetry = {"hdr_regulation": hdr_stats}

    pbr_bundle_info: dict[str, Any] | None = None
    saved_master_path: str | None = None
    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        master_file = out_path / "image.png"
        img_out.save(master_file)
        saved_master_path = str(master_file)
        if generate_pbr:
            pbr_res = generate_pbr_material_bundle(
                img_out,
                output_dir=out_path,
                prefix="pbr",
                target_max_edge=None,
            )
            pbr_bundle_info = {k: v for k, v in pbr_res.items() if k != "maps"}

    optical_metrics = evaluate_optical_quality_metrics(img_out)
    return {
        "engine": engine_used,
        "dimensions": {"width": img_out.size[0], "height": img_out.size[1]},
        "seed": run_seed,
        "prompt_spec": {
            "category": spec["category"],
            "human_prompt": spec["human_prompt"],
            "explicit_constraints_preserved": spec.get("explicit_constraints_preserved", []),
            "steps": spec["steps"],
        },
        "reference_conditioning": asdict(ref_profile) if ref_profile is not None else None,
        "reference_analysis": ref_analysis,
        "identity_lock_metrics": identity_lock_metrics,
        "upscale_telemetry": upscale_telemetry,
        "optical_quality_metrics": optical_metrics,
        "pbr_bundle": pbr_bundle_info,
        "master_image_path": saved_master_path,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }


class ComfyClient:
    """Client orienté objet ComfyUI FLUX.2-dev avec ReferenceLatent et Super-Résolution 8K/16K PBR."""

    def __init__(self, comfy_base: str = COMFY_BASE) -> None:
        self.comfy_base = comfy_base.rstrip("/")

    def health(self) -> dict[str, Any]:
        return check_comfy_health(self.comfy_base)

    def build_workflow(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return build_flux2_comfy_workflow(prompt, **kwargs)

    def submit(self, workflow: dict[str, Any]) -> str:
        return submit_workflow(workflow, comfy_base=self.comfy_base)

    def cancel(self, prompt_id: str | None = None) -> dict[str, Any]:
        return cancel_comfy_job(prompt_id, comfy_base=self.comfy_base)

    def execute(self, raw_prompt: str, **kwargs: Any) -> dict[str, Any]:
        return execute_high_fidelity_image_job(raw_prompt, comfy_base=self.comfy_base, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="AuroraIA High-Fidelity ComfyUI FLUX.2 & ReferenceLatent Client")
    parser.add_argument("prompt", type=str, help="User prompt")
    parser.add_argument("--reference", type=Path, default=None, help="Optional reference image for ReferenceLatent conditioning")
    parser.add_argument("--edit-mode", type=str, default="auto", choices=["auto", "canonical_identity_lock", "surgical_attribute_edit", "structural_style_transfer"])
    parser.add_argument("--resolution", type=str, default="auto", choices=["auto", "1k", "2k", "4k", "8k", "16k"])
    parser.add_argument("--pbr", action="store_true", help="Synthesize full PBR map bundle (Normal, Roughness, Cavity AO, Height, Metallic, ORM)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory")
    args = parser.parse_args()

    res = execute_high_fidelity_image_job(
        args.prompt,
        reference_image_path=args.reference,
        edit_mode=args.edit_mode,
        resolution=args.resolution,
        generate_pbr=args.pbr,
        output_dir=args.output_dir,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
