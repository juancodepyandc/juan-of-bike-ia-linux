"""Unified multi-module progress tracking and stage coordinator for Aurora Python services.

Architecture Contract:
Every module execution follows the universal 4-macro-phase lifecycle:
  1. ANALYSE (0% - 25%)      : Intention, Cadrage, Storyboard, Preflight, Références
  2. REALISATION (25% - 70%)  : Génération, Synthèse, Cuisson, Inférénce, Rendu, Compilation
  3. VERIFICATION (70% - 90%) : Validation, Tests, Sandbox, Juge de vision, Contrôle qualité
  4. FINALISATION (90% - 100%): Packaging, Post-traitement, Export livrable, Métadonnées

Progress protocol:
  Emits stdout lines in the format:
    PROGRESS:{"module":"...","stage":"...","stage_label":"...","sub_stage":"...","pct":float,"detail":"...","step":int,"total_steps":int,"ts":float}
  And for legacy tailers:
    PROGRESS:<stage>:<detail>
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Callable


@dataclass
class StageDefinition:
    key: str
    label: str
    pct_start: float
    pct_end: float
    description: str


# Canonical stages per module
MODULE_STAGE_DEFINITIONS: dict[str, list[StageDefinition]] = {
    "3d": [
        StageDefinition("analyse", "Analyse & Concept", 0.0, 20.0, "Analyse du prompt et synthèse des vues de référence FLUX"),
        StageDefinition("realisation", "Génération 3D & PBR", 20.0, 70.0, "Génération maillage Hunyuan3D/Trellis, retopologie et textures PBR"),
        StageDefinition("verification", "Contrôle Qualité & Juge IA", 70.0, 90.0, "Tests d étanchéité, fidélité et validation par juge vision"),
        StageDefinition("finalisation", "Finalisation & Export GLB", 90.0, 100.0, "Injection cinématique, rendu vignettes et export GLB canonique"),
    ],
    "video": [
        StageDefinition("analyse", "Analyse & Storyboard", 0.0, 20.0, "Découpage des plans, keyframes FLUX et direction artistique"),
        StageDefinition("realisation", "Rendu Vidéo & Audio", 20.0, 70.0, "Diffusion Wan2.2, synthèse vocale et synchronisation labiale"),
        StageDefinition("verification", "Contrôle Qualité & Raccords", 70.0, 85.0, "Contrôle de fluidité, raccord des coutures et audit esthétique"),
        StageDefinition("finalisation", "Montage & Export Master", 85.0, 100.0, "Upscaling Real-ESRGAN, assemblage MP4 et sous-titres"),
    ],
    "code": [
        StageDefinition("analyse", "Analyse & Cadrage", 0.0, 25.0, "Classification d intention, preflight machine et plan d architecture"),
        StageDefinition("realisation", "Génération Agentique", 25.0, 70.0, "Production des fichiers source WS3 et intégration des assets"),
        StageDefinition("verification", "Sandbox & Qualité", 70.0, 90.0, "Exécution sandbox, tests unitaires, validation statique et auto-correction"),
        StageDefinition("finalisation", "Packaging & Livraison", 90.0, 100.0, "Fichiers support, manifest et validation de conformité"),
    ],
    "voix": [
        StageDefinition("analyse", "Analyse & Phonémisation", 0.0, 25.0, "Segmentation texte, phonémisation FR et analyse prosodique"),
        StageDefinition("realisation", "Synthèse & Clonage", 25.0, 70.0, "Inférence TTS, adaptation de timbre et génération acoustique"),
        StageDefinition("verification", "Contrôle Spectral", 70.0, 90.0, "Contrôle du rapport signal/bruit, clarté et dynamique"),
        StageDefinition("finalisation", "Masterisation & Export", 90.0, 100.0, "Normalisation LUFS, export WAV/MP3 et métadonnées"),
    ],
    "image": [
        StageDefinition("analyse", "Analyse & Composition", 0.0, 20.0, "Règles de composition, cadrage et prompt engineering"),
        StageDefinition("realisation", "Génération Visuelle", 20.0, 70.0, "Débruitage latent FLUX/SDXL et passes de raffinement"),
        StageDefinition("verification", "Contrôle & Restauration", 70.0, 90.0, "Restauration visage, détourage et juge d esthétique"),
        StageDefinition("finalisation", "Export & Métadonnées", 90.0, 100.0, "Export haute définition et archivage projet"),
    ],
    "cowork": [
        StageDefinition("analyse", "Cadrage & Clarification", 0.0, 25.0, "Extraction de contexte, clarification des contraintes et plan d action"),
        StageDefinition("realisation", "Recherche & Rédaction", 25.0, 75.0, "Recherche web, synthèse documentaire et production"),
        StageDefinition("verification", "Revue & Cohérence", 75.0, 90.0, "Vérification des faits, contrôle de structure et audit"),
        StageDefinition("finalisation", "Livrable & Archivage", 90.0, 100.0, "Mise en page, export documents et métadonnées"),
    ],
    "cyber": [
        StageDefinition("analyse", "Reconnaissance & Cibles", 0.0, 25.0, "Inventaire de surface d attaque et cartographie"),
        StageDefinition("realisation", "Scan & Détection", 25.0, 70.0, "Audit automatisé des vulnérabilités et configurations"),
        StageDefinition("verification", "Validation des Failles", 70.0, 90.0, "Tri des faux positifs, évaluation de criticité CVSS"),
        StageDefinition("finalisation", "Rapport & Remédiation", 90.0, 100.0, "Génération du rapport d audit et plan correctif"),
    ],
    "conversation": [
        StageDefinition("analyse", "Compréhension du Contexte", 0.0, 25.0, "Analyse sémantique et mémoire conversationnelle"),
        StageDefinition("realisation", "Raisonnement & Réponse", 25.0, 80.0, "Inférence LLM et enrichissement multi-outils"),
        StageDefinition("verification", "Cohérence & Ton", 80.0, 95.0, "Vérification de pertinence et sécurité"),
        StageDefinition("finalisation", "Restitution", 95.0, 100.0, "Formatage et transmission du message"),
    ],
}


class ProgressTracker:
    """Manages smooth, calibrated progress tracking for a module task."""

    def __init__(
        self,
        module: str,
        project_name: str = "default",
        total_steps: int = 1,
        on_emit: Callable[[dict], None] | None = None,
    ):
        self.module = module.lower()
        self.project_name = project_name
        self.total_steps = max(1, total_steps)
        self.current_step = 0
        self.current_pct = 0.0
        self.current_stage = "analyse"
        self.current_stage_label = "Analyse"
        self.current_sub_stage = "init"
        self.current_detail = "Initialisation..."
        self.start_time = time.time()
        self.last_emit_time = self.start_time
        self.on_emit = on_emit

        self.stages = MODULE_STAGE_DEFINITIONS.get(self.module, MODULE_STAGE_DEFINITIONS["3d"])
        self.stage_map = {s.key: s for s in self.stages}

    def _find_stage_for_pct(self, pct: float) -> StageDefinition:
        for s in self.stages:
            if s.pct_start <= pct <= s.pct_end:
                return s
        return self.stages[-1]

    def emit(
        self,
        stage: str | None = None,
        sub_stage: str | None = None,
        pct: float | None = None,
        detail: str | None = None,
        step: int | None = None,
    ) -> dict:
        """Emit a calibrated progress update."""
        now = time.time()
        if step is not None:
            self.current_step = step

        if stage and stage in self.stage_map:
            st_def = self.stage_map[stage]
            self.current_stage = st_def.key
            self.current_stage_label = st_def.label
            if pct is None:
                pct = st_def.pct_start

        if pct is not None:
            self.current_pct = max(self.current_pct, min(100.0, float(pct)))
            st_def = self._find_stage_for_pct(self.current_pct)
            self.current_stage = st_def.key
            self.current_stage_label = st_def.label

        if sub_stage:
            self.current_sub_stage = sub_stage
        if detail:
            self.current_detail = detail

        payload = {
            "module": self.module,
            "project": self.project_name,
            "stage": self.current_stage,
            "stage_label": self.current_stage_label,
            "sub_stage": self.current_sub_stage,
            "pct": round(self.current_pct, 1),
            "detail": self.current_detail,
            "step": self.current_step,
            "total_steps": self.total_steps,
            "elapsed_s": round(now - self.start_time, 1),
            "ts": round(now, 3),
        }

        json_line = f"PROGRESS:{json.dumps(payload, ensure_ascii=False)}"
        print(json_line, flush=True)

        self.last_emit_time = now
        if self.on_emit:
            self.on_emit(payload)

        return payload

    def step_progress(
        self,
        stage: str,
        sub_stage: str,
        step_index: int,
        total_sub_steps: int,
        detail: str,
    ) -> dict:
        """Calculate progress within a stage based on sub-step index."""
        st_def = self.stage_map.get(stage, self._find_stage_for_pct(self.current_pct))
        fraction = max(0.0, min(1.0, float(step_index) / max(1, total_sub_steps)))
        pct = st_def.pct_start + fraction * (st_def.pct_end - st_def.pct_start)
        return self.emit(stage=stage, sub_stage=sub_stage, pct=pct, detail=detail, step=step_index)

    def heartbeat(self, max_increment: float = 0.5, cap_pct: float | None = None) -> dict:
        """Emit a small heartbeat progress tick during long operations."""
        st_def = self._find_stage_for_pct(self.current_pct)
        stage_ceiling = cap_pct if cap_pct is not None else (st_def.pct_end - 0.5)
        if self.current_pct < stage_ceiling:
            next_pct = min(stage_ceiling, self.current_pct + max_increment)
            return self.emit(pct=next_pct, detail=self.current_detail)
        return self.emit()

    def complete(self, detail: str = "Tâche terminée avec succès.") -> dict:
        """Mark task as 100% complete."""
        final_stage = self.stages[-1].key
        return self.emit(stage=final_stage, sub_stage="done", pct=100.0, detail=detail, step=self.total_steps)


_trackers: dict[str, ProgressTracker] = {}


def get_progress_tracker(module: str, project_name: str = "default", total_steps: int = 1) -> ProgressTracker:
    key = f"{module.lower()}:{project_name}"
    if key not in _trackers:
        _trackers[key] = ProgressTracker(module, project_name, total_steps)
    return _trackers[key]


def emit_module_progress(
    module: str,
    stage: str,
    sub_stage: str = "working",
    pct: float | None = None,
    detail: str = "",
    project_name: str = "default",
) -> dict:
    """Convenience function to emit a progress event directly."""
    tracker = get_progress_tracker(module, project_name)
    return tracker.emit(stage=stage, sub_stage=sub_stage, pct=pct, detail=detail)
