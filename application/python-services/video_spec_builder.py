"""video_spec_builder — le SEUL endroit qui transforme une intention utilisateur
en `VideoJobSpec` résolue.

Chemins d'appel qui doivent tous passer par ici :
  1. UI Tauri / navigateur → bridge → build_spec_from_intent()
  2. Bridge `/api/cinema/generate` (film multi-plans) → build_spec_from_shot()
  3. Bridge `/api/video/render` (rendu direct 1 plan) → build_spec_from_intent()
  4. CLI `video_render --prompt "..."` → build_spec_from_intent()
  5. CLI `video_render --spec <fichier.json>` → charge directement une spec

Toute logique de résolution (durée, aspect, motion suffix, seed déterministe,
grille frames/pixels, mapping quality_mode) vit ici — pas en TypeScript, pas
en Rust, pas dupliquée. Le TS peut appeler ce module via le bridge et afficher
la spec résolue avant lancement (`--print-spec` équivalent en HTTP).
"""

from __future__ import annotations

import hashlib
from typing import Optional

from video_job_spec import (
    VideoJobSpec,
    align_frames,
    align_to_grid,
    DEFAULT_FPS,
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_MOTION_INTERP,
    DEFAULT_MODEL_ID,
    DEFAULT_NUM_INFERENCE_STEPS,
    DEFAULT_QUALITY_MODE,
    DEFAULT_FORCE_STRATEGY,
    DEFAULT_PROFILE,
    PIXEL_GRID,
)


# ── résolution native par (aspect, quality_mode) ───────────────────────
# Wan 2.2 TI2V-5B a été entraîné à des tailles précises. Toute génération hors
# de cette distribution produit des artefacts documentés (structures dupliquées,
# horizons répétés, cf. loi §4.4a du PROMPT_REFONTE_MODULE_VIDEO). L'UI ne doit
# JAMAIS choisir arbitrairement une résolution — elle indique l'aspect et le
# profil de qualité, le builder mappe sur une résolution native connue.

NATIVE_RESOLUTIONS = {
    # (aspect, quality_mode) -> (native_w, native_h)
    ("16:9", "premium"):   (1280, 720),   # Wan native FHD
    ("16:9", "balanced"):  (832, 480),    # Wan native SD — journal known-good
    ("16:9", "auto"):      (832, 480),
    ("9:16", "premium"):   (720, 1280),
    ("9:16", "balanced"):  (480, 832),
    ("9:16", "auto"):      (480, 832),
    ("1:1", "premium"):    (960, 960),
    ("1:1", "balanced"):   (704, 704),
    ("1:1", "auto"):       (704, 704),
    ("4:3", "premium"):    (1024, 768),
    ("4:3", "balanced"):   (832, 640),
    ("4:3", "auto"):       (832, 640),
}

# Cibles de livraison (upscaler post) par quality_mode.
DELIVERED_RESOLUTIONS = {
    # (aspect, quality_mode) -> (delivered_w, delivered_h)
    ("16:9", "premium"):   (3840, 2160),   # 4K
    ("16:9", "balanced"):  (1920, 1080),   # FHD
    ("16:9", "auto"):      (1920, 1080),
    ("9:16", "premium"):   (2160, 3840),
    ("9:16", "balanced"):  (1080, 1920),
    ("9:16", "auto"):      (1080, 1920),
    ("1:1", "premium"):    (2160, 2160),
    ("1:1", "balanced"):   (1080, 1080),
    ("1:1", "auto"):       (1080, 1080),
    ("4:3", "premium"):    (2880, 2160),
    ("4:3", "balanced"):   (1440, 1080),
    ("4:3", "auto"):       (1440, 1080),
}

# Steps par quality_mode — mesuré au banc (2026-08-07) : 20-60 varie de 3.5 %
# sur netteté. `personal_quality_first` prend le haut de la plage utile.
STEPS_BY_QUALITY = {
    "premium":  60,
    "balanced": 40,
    "auto":     50,
}

DEFAULT_ASPECT = "16:9"


def _deterministic_seed_from_prompt(prompt: str) -> int:
    """Seed reproductible dérivée du prompt (FNV-1a 32 bits comme en TS).

    Cause : sans seed fixée, le banc 2026-08-07 a mesuré 165 % de variance
    sur l'amplitude de mouvement pour trois seeds au même prompt. Ne pas
    fixer de seed = loterie sur « ça bouge ou pas ». La dérivation depuis
    le prompt donne : même prompt → même vidéo (relance = idem),
    prompt différent → seed différente.
    """
    h = 0x811c9dc5
    for ch in prompt:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h % 2147483647


def _resolve_seconds_to_frames(seconds: float, fps: int = DEFAULT_FPS) -> int:
    """Combien de frames pour cette durée, alignées sur la grille 8k+1."""
    raw = int(round(max(0.5, float(seconds)) * fps))
    return align_frames(raw)


def _compose_prompt(
    prompt: str,
    *,
    motion_suffix: str = "",
    cinematography: str = "",
    style_suffix: str = "",
    reference_contract: str = "",
) -> str:
    """Assemble le prompt final tel qu'envoyé au modèle.

    Ordre canonique déterministe — c'est ce qui garantit que deux appelants
    qui composent « le même prompt final » avec la même intention aboutissent
    à la même chaîne exacte. L'UI faisait ça en JS (VideoView.tsx :425-484),
    la CLI ne l'a jamais fait — d'où le même prompt utilisateur qui produisait
    deux prompts modèle différents.
    """
    parts = [prompt.strip()]
    if reference_contract.strip():
        parts.append(reference_contract.strip())
    if cinematography.strip():
        parts.append(cinematography.strip())
    if style_suffix.strip():
        parts.append(style_suffix.strip())
    if motion_suffix.strip():
        parts.append(f"Motion directive: {motion_suffix.strip()}")
    return "\n\n".join(p for p in parts if p)


def build_spec_from_intent(
    *,
    prompt: str,
    aspect: str = DEFAULT_ASPECT,
    duration_s: Optional[float] = None,
    num_frames: Optional[int] = None,
    quality_mode: str = DEFAULT_QUALITY_MODE,
    seed: Optional[int] = None,
    image_path: Optional[str] = None,
    motion_suffix: str = "",
    cinematography: str = "",
    style_suffix: str = "",
    reference_contract: str = "",
    negative_prompt: Optional[str] = None,
    force_strategy: str = DEFAULT_FORCE_STRATEGY,
    motion_interp: int = DEFAULT_MOTION_INTERP,
    model_id: str = DEFAULT_MODEL_ID,
    profile: str = DEFAULT_PROFILE,
    fps: int = DEFAULT_FPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    num_inference_steps: Optional[int] = None,
) -> VideoJobSpec:
    """Construit une VideoJobSpec depuis une intention utilisateur.

    C'est la fonction que TOUT chemin d'appel doit utiliser. Elle applique
    les défauts, la grille, la dérivation seed, la composition du prompt.
    Elle refuse (ValueError) toute intention qui ne peut PAS être satisfaite
    plutôt que de la corriger silencieusement.
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt vide — l'intention doit contenir du texte")

    if aspect not in {a for (a, _) in NATIVE_RESOLUTIONS}:
        raise ValueError(f"aspect {aspect!r} non supporté — options: 16:9, 9:16, 1:1, 4:3")

    if quality_mode not in {"auto", "balanced", "premium"}:
        raise ValueError(f"quality_mode {quality_mode!r} invalide")

    # Géométrie native → livraison.
    native_w, native_h = NATIVE_RESOLUTIONS[(aspect, quality_mode)]
    delivered_w, delivered_h = DELIVERED_RESOLUTIONS[(aspect, quality_mode)]
    # Réalignement paranoïaque : la table est déjà alignée mais on protège
    # contre tout futur ajout non aligné à la grille 32.
    native_w = align_to_grid(native_w, PIXEL_GRID)
    native_h = align_to_grid(native_h, PIXEL_GRID)

    # Frames.
    if num_frames is not None:
        n_frames = align_frames(int(num_frames))
    elif duration_s is not None:
        n_frames = _resolve_seconds_to_frames(float(duration_s), fps=fps)
    else:
        # Défaut : 65 frames ≈ 2,7 s à 24 fps — c'est la baseline journal.
        n_frames = 65

    # Steps.
    steps = int(num_inference_steps) if num_inference_steps is not None else STEPS_BY_QUALITY[quality_mode]

    # Seed déterministe si absent.
    if seed is None:
        # Le hash tient compte du prompt COMPOSÉ pour que motion_suffix / style
        # changent aussi la seed — sinon deux presets motion différents sur
        # le même prompt utilisateur héritent de la même seed et paraissent
        # « bizarrement les mêmes ».
        temp_composed = _compose_prompt(
            prompt,
            motion_suffix=motion_suffix,
            cinematography=cinematography,
            style_suffix=style_suffix,
            reference_contract=reference_contract,
        )
        seed_val = _deterministic_seed_from_prompt(temp_composed)
    else:
        seed_val = int(seed)

    prompt_composed = _compose_prompt(
        prompt,
        motion_suffix=motion_suffix,
        cinematography=cinematography,
        style_suffix=style_suffix,
        reference_contract=reference_contract,
    )

    spec = VideoJobSpec(
        prompt=prompt,
        prompt_composed=prompt_composed,
        negative_prompt=negative_prompt,
        width=native_w,
        height=native_h,
        delivered_width=delivered_w,
        delivered_height=delivered_h,
        num_frames=n_frames,
        fps=fps,
        model_id=model_id,
        num_inference_steps=steps,
        guidance_scale=float(guidance_scale),
        quality_mode=quality_mode,
        force_strategy=force_strategy,
        motion_interp=int(motion_interp),
        profile=profile,
        seed=seed_val,
        image_path=image_path,
    )
    spec.validate()
    return spec


def build_spec_from_shot(
    *,
    shot: dict,
    storyboard: dict,
    anchor_image: Optional[str] = None,
) -> VideoJobSpec:
    """Construit une VideoJobSpec pour UN plan d'un storyboard.

    Adapte le contrat storyboard (multi-plans, résolution globale, style
    partagé) à la spec canonique par plan. C'est ce qu'appelle le futur
    adaptateur `/api/cinema/generate` par plan.
    """
    aspect = str(storyboard.get("aspect") or DEFAULT_ASPECT)
    quality_mode = str(storyboard.get("quality_mode") or DEFAULT_QUALITY_MODE)
    style = str(storyboard.get("style") or "realistic")
    scene = str(shot.get("scene") or "")
    action_contract = str(shot.get("action_contract") or "")
    duration_s = float(shot.get("duration_s") or 5.0)
    camera = str(shot.get("camera") or "")

    # Un plan avec dialogue peut hériter d'une seed explicite ; sinon on
    # dérive de manière déterministe depuis le shot_id (comme le fait
    # actuellement cinema_pipeline:4590 : 1000 + shot_id*31), pour que la
    # relance d'un plan précis donne bien la même vidéo.
    shot_seed = shot.get("seed")
    if shot_seed is None:
        try:
            shot_id = int(shot.get("id") or 0)
            shot_seed = 1000 + (shot_id * 31)
        except Exception:
            shot_seed = None  # fallback → dérivation depuis prompt

    prompt = f"{scene}"
    reference_contract = (
        f"The action already in progress: {action_contract}"
        if action_contract else ""
    )

    return build_spec_from_intent(
        prompt=prompt,
        aspect=aspect,
        duration_s=duration_s,
        quality_mode=quality_mode,
        seed=shot_seed,
        image_path=anchor_image,
        cinematography=camera,
        style_suffix=f"style: {style}" if style else "",
        reference_contract=reference_contract,
        negative_prompt=shot.get("negative_prompt"),
    )
