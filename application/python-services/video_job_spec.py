"""VideoJobSpec — contrat CANONIQUE d'un rendu vidéo (WS-V-P § parité).

C'est le seul objet qu'un rendu vidéo doit produire ou consommer, quel que
soit le chemin d'appel (UI Tauri, bridge, tunnel Cloudflare, CLI). Deux
requêtes qui décrivent la même vidéo doivent produire des `VideoJobSpec`
canoniquement identiques → même `spec_hash`. C'est la mécanique par
laquelle « le même bouton dans l'UI et la même commande CLI et le même
appel tunnel » produisent réellement la même vidéo, plutôt que « à peu
près la même » (défaut historique documenté dans PROMPT_REFONTE_MODULE_VIDEO
§3.3).

Discipline :
- champs typés stricts (dataclass), pas de dict libres,
- pas de valeur silencieuse par défaut (les défauts SONT posés ici, une
  fois pour toutes ; les paths d'appel ne peuvent pas les rejouer
  différemment),
- sérialisation déterministe (sort_keys, séparateurs sans espace, floats
  normalisés) → sha256 stable, indépendant de la plateforme et de
  l'ordre d'insertion,
- schéma versionné : bumper `SPEC_VERSION` invalide tous les hashes
  antérieurs — c'est voulu (deux versions ne sont plus la même vidéo).

Le schéma JSON est fourni par `to_json_schema()` — utilisable côté TS pour
valider le contrat avant envoi bridge.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

SPEC_VERSION = 1


# ── défauts uniques ────────────────────────────────────────────────────
# Ces valeurs sont la source de vérité. Toute divergence entre paths
# d'appel a été mesurée comme une cause de « pourquoi c'est différent
# selon le bouton cliqué » (cf. journal 2026-08-07 sur la variance
# seed 165 %). Défauts alignés sur `personal_quality_first` (§ profil).

DEFAULT_MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
DEFAULT_QUALITY_MODE = "auto"          # → premium en pratique sur 16 Go
DEFAULT_FPS = 24                       # cadence native TI2V-5B
DEFAULT_MOTION_INTERP = 1              # ffmpeg minterpolate 48 fps
DEFAULT_GUIDANCE_SCALE = 4.5           # Wan 5B I2V, mesuré ± 3 % dans [3,6]
DEFAULT_NUM_INFERENCE_STEPS = 60       # premium journal, quality-first
DEFAULT_FORCE_STRATEGY = "auto"
DEFAULT_PROFILE = "personal_quality_first"

# Grille native Wan/LTX : 8k+1 frames + multiple de 32 en pixel.
FRAME_GRID_ANCHOR = 8   # frames = 8*n + 1
FRAME_MIN = 25          # ~1,04 s à 24 fps
FRAME_MAX_SEGMENT = 97  # cap segment Wan
PIXEL_GRID = 32

VALID_QUALITY_MODES = {"auto", "balanced", "premium"}
VALID_MOTION_INTERP = {"0", "1", "2", 0, 1, 2}
VALID_FORCE_STRATEGY = {"auto", "wan5b", "ltx"}


def align_to_grid(value: int, grid: int) -> int:
    return max(grid, round(value / grid) * grid)


def align_frames(value: int) -> int:
    v = max(FRAME_MIN, int(value))
    v = min(FRAME_MAX_SEGMENT, v)
    # 8k + 1
    return max(FRAME_MIN, ((v - 1) // FRAME_GRID_ANCHOR) * FRAME_GRID_ANCHOR + 1)


@dataclass
class VideoJobSpec:
    """Contrat canonique d'un rendu vidéo (v1)."""

    # ── entrée narrative ──
    prompt: str                                # texte utilisateur brut
    prompt_composed: str                       # texte final envoyé au modèle
                                                # (motion suffix, cinématographie,
                                                #  contrat de référence,
                                                #  distillation LLM)
    negative_prompt: Optional[str] = None

    # ── géométrie ──
    width: int = 832                           # génération native
    height: int = 480
    delivered_width: int = 1280                # après upscale de livraison
    delivered_height: int = 720
    num_frames: int = 65
    fps: int = DEFAULT_FPS

    # ── modèle et qualité ──
    model_id: str = DEFAULT_MODEL_ID
    num_inference_steps: int = DEFAULT_NUM_INFERENCE_STEPS
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE
    quality_mode: str = DEFAULT_QUALITY_MODE
    force_strategy: str = DEFAULT_FORCE_STRATEGY
    motion_interp: int = DEFAULT_MOTION_INTERP
    profile: str = DEFAULT_PROFILE

    # ── détermination ──
    # seed : OBLIGATOIRE (typé int, non-nullable). Pas de seed = loterie
    # motion 165 % (banc isolation 2026-08-07). Le builder dérive une
    # seed déterministe du prompt si l'appelant n'en fournit pas.
    seed: int = 0

    # ── i2v optionnel ──
    image_path: Optional[str] = None           # ancre i2v, chemin absolu

    # ── métadonnées ──
    spec_version: int = SPEC_VERSION
    created_at: float = field(default_factory=time.time)

    # ── validation ──
    def validate(self) -> None:
        """Lève ValueError sur toute incohérence structurelle."""
        if self.spec_version != SPEC_VERSION:
            raise ValueError(
                f"spec_version={self.spec_version} incompatible with runtime "
                f"SPEC_VERSION={SPEC_VERSION}"
            )
        if not self.prompt or not self.prompt.strip():
            raise ValueError("prompt vide")
        if not self.prompt_composed or not self.prompt_composed.strip():
            raise ValueError("prompt_composed vide")
        if self.width % PIXEL_GRID != 0 or self.height % PIXEL_GRID != 0:
            raise ValueError(
                f"width×height doit être aligné sur {PIXEL_GRID} — "
                f"reçu {self.width}×{self.height}"
            )
        if self.num_frames < FRAME_MIN or self.num_frames > FRAME_MAX_SEGMENT:
            raise ValueError(
                f"num_frames={self.num_frames} hors [{FRAME_MIN}, {FRAME_MAX_SEGMENT}]"
            )
        if (self.num_frames - 1) % FRAME_GRID_ANCHOR != 0:
            raise ValueError(
                f"num_frames={self.num_frames} doit vérifier (n-1) % "
                f"{FRAME_GRID_ANCHOR} == 0 (grille Wan/LTX)"
            )
        if self.fps <= 0 or self.fps > 120:
            raise ValueError(f"fps={self.fps} hors bornes raisonnables")
        if self.num_inference_steps < 1 or self.num_inference_steps > 200:
            raise ValueError(f"num_inference_steps={self.num_inference_steps} hors [1, 200]")
        if self.guidance_scale < 0.0 or self.guidance_scale > 20.0:
            raise ValueError(f"guidance_scale={self.guidance_scale} hors [0, 20]")
        if self.quality_mode not in VALID_QUALITY_MODES:
            raise ValueError(
                f"quality_mode={self.quality_mode!r} not in {sorted(VALID_QUALITY_MODES)}"
            )
        if self.motion_interp not in {0, 1, 2}:
            raise ValueError(
                f"motion_interp={self.motion_interp} not in {{0,1,2}}"
            )
        if self.force_strategy not in VALID_FORCE_STRATEGY:
            raise ValueError(
                f"force_strategy={self.force_strategy!r} not in {sorted(VALID_FORCE_STRATEGY)}"
            )
        if not isinstance(self.seed, int) or self.seed < 0 or self.seed > 2**31 - 1:
            raise ValueError(
                f"seed doit être un int dans [0, 2^31-1], reçu {self.seed!r}"
            )
        if self.delivered_width < self.width or self.delivered_height < self.height:
            # Livraison plus petite que native = perte — on n'a jamais raison
            # de le faire (l'upscale coûte 0 en information si égal, positif
            # sinon). C'est symptomatique d'un builder cassé.
            raise ValueError(
                f"delivered ({self.delivered_width}×{self.delivered_height}) "
                f"< native ({self.width}×{self.height}) — upscale de livraison "
                f"doit être ≥ 1×1"
            )

    def to_canonical_dict(self) -> dict:
        """Représentation canonique, excluant created_at (variable dans le temps).

        Le hash NE dépend PAS de created_at : deux specs identiques rendues à
        deux moments doivent produire le même hash.
        """
        d = asdict(self)
        d.pop("created_at", None)
        # Normalise les floats à 6 décimales — évite qu'un `4.5` vs `4.500000`
        # côté TS/Python ne produise deux hashes.
        for k, v in list(d.items()):
            if isinstance(v, float):
                d[k] = round(v, 6)
        return d

    def spec_hash(self) -> str:
        """sha256 déterministe de la spec canonique."""
        payload = json.dumps(
            self.to_canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["spec_hash"] = self.spec_hash()
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


def from_dict(data: dict) -> VideoJobSpec:
    """Reconstruit une VideoJobSpec depuis un dict JSON (rejet strict)."""
    # Filtre : n'accepte que les champs déclarés du dataclass.
    fields = {f.name for f in dataclasses.fields(VideoJobSpec)}
    payload = {k: v for k, v in data.items() if k in fields}
    spec = VideoJobSpec(**payload)
    spec.validate()
    return spec


def to_json_schema() -> dict:
    """Schéma JSON du contrat (utilisable côté TS pour valider avant envoi).

    Volontairement plat et permissif sur les champs optionnels — c'est
    `validate()` qui applique les règles fines (grille frames, plage seed).
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "VideoJobSpec",
        "type": "object",
        "required": [
            "prompt", "prompt_composed",
            "width", "height", "num_frames", "fps",
            "num_inference_steps", "guidance_scale",
            "quality_mode", "motion_interp", "seed",
            "spec_version",
        ],
        "properties": {
            "prompt": {"type": "string", "minLength": 1},
            "prompt_composed": {"type": "string", "minLength": 1},
            "negative_prompt": {"type": ["string", "null"]},
            "width": {"type": "integer", "minimum": PIXEL_GRID, "multipleOf": PIXEL_GRID},
            "height": {"type": "integer", "minimum": PIXEL_GRID, "multipleOf": PIXEL_GRID},
            "delivered_width": {"type": "integer", "minimum": PIXEL_GRID},
            "delivered_height": {"type": "integer", "minimum": PIXEL_GRID},
            "num_frames": {"type": "integer", "minimum": FRAME_MIN, "maximum": FRAME_MAX_SEGMENT},
            "fps": {"type": "integer", "minimum": 1, "maximum": 120},
            "model_id": {"type": "string", "minLength": 1},
            "num_inference_steps": {"type": "integer", "minimum": 1, "maximum": 200},
            "guidance_scale": {"type": "number", "minimum": 0.0, "maximum": 20.0},
            "quality_mode": {"type": "string", "enum": sorted(VALID_QUALITY_MODES)},
            "force_strategy": {"type": "string", "enum": sorted(VALID_FORCE_STRATEGY)},
            "motion_interp": {"type": "integer", "enum": [0, 1, 2]},
            "profile": {"type": "string"},
            "seed": {"type": "integer", "minimum": 0, "maximum": 2**31 - 1},
            "image_path": {"type": ["string", "null"]},
            "spec_version": {"type": "integer", "const": SPEC_VERSION},
        },
    }
