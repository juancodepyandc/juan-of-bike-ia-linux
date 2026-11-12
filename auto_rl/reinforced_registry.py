"""Registre unifié des Modèles Renforcés (`modele/renforce/`) et génération automatique des bilans `.md`.

Contrat architectural :
1. Les modèles de base (`modele/huggingface/`, `modele/comfyui/`, modèles Ollama officiels)
   sont 100 % INTOUCHABLES (vérifiés par empreinte SHA-256 / inode dans `base_manifest.json`).
2. Tous les poids entraînés / adaptateurs LoRA / sous-espaces de poids vont exclusivement dans :
   `/home/juan/AuroraIA/modele/renforce/<module>/`
3. Chaque module dispose de son propre fichier `/home/juan/AuroraIA/modele/renforce/<module>/GAINS.md`
   et le registre global `/home/juan/AuroraIA/modele/renforce/GAINS_MODELES_RENFORCES.md` récapitule
   les gains mesurés par axe (Précision géométrique, Topologie manifold / Auto-intersections,
   Style & Fidélité multi-vues, Cohérence face arrière / pire vue, Assemblage, Exactitude Code/Cyber, etc.).
"""
from __future__ import annotations

import json
import math
import os
import shutil
import statistics
import time
from pathlib import Path
from typing import Any

from .config import LABELS, ROOT, STATE, defaults
from .storage import atomic_json, file_hash, read_json

RENFORCE_ROOT = ROOT / "modele" / "renforce"

# `reinforced_available` is reserved for an adapter that went through the promotion
# gate (official entry in `<state>/registry/<module>.json`). A measured adapter that
# was not promoted keeps its audit numbers under `candidate_not_promoted`.
PROMOTED_STATUS = "reinforced_available"
CANDIDATE_STATUS = "candidate_not_promoted"
NON_MESURE = "non mesuré"
# Prepended to a Markdown sheet read from disk when the stored status it was rendered
# from (`reinforced_available`) is not confirmed by the official registry.
STALE_SHEET_NOTICE = (
    "> ⚠️ **Fiche à régénérer.** Elle affiche un statut « disponible / vérifié » que le registre officiel ne confirme "
    "pas : l'adaptateur concerné est un **candidat non promu** et le modèle de base reste servi. Les mentions "
    "« vérifié » ou « champion » ne valent pas promotion, et ses chiffres de rigging, s'il y en a, n'ont jamais "
    "été mesurés.\n\n"
)


def _num(value: Any) -> float | None:
    """A finite measured number, or None. A missing value is never replaced by a literal."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _fmt(value: Any, spec: str = ".3f", unit: str = "") -> str:
    """Format a measured number for the French reports; anything else reads « non mesuré »."""
    number = _num(value)
    return NON_MESURE if number is None else f"{number:{spec}}{unit}"


def _scaled(value: Any, factor: float, digits: int) -> float | None:
    number = _num(value)
    return None if number is None else round(number * factor, digits)


def _delta(after: Any, before: Any, factor: float, digits: int) -> float | None:
    a, b = _num(after), _num(before)
    return None if a is None or b is None else round((a - b) * factor, digits)


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def sign_test_two_sided(wins: Any, losses: Any) -> float | None:
    """Exact two-sided sign test on paired wins/losses (ties excluded); None when not computable."""
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (wins, losses)) or wins + losses == 0:
        return None
    total, extreme = wins + losses, max(wins, losses)
    tail = sum(math.comb(total, k) for k in range(extreme, total + 1)) / 2 ** total
    return min(1.0, 2.0 * tail)


def sign_test_sentence(wins: Any, losses: Any) -> str:
    """French reading of the sign test, or an empty string when it cannot be computed."""
    p_value = sign_test_two_sided(wins, losses)
    if p_value is None:
        return ""
    reading = ("non distinguable d'une absence de changement au seuil de 5 %" if p_value >= 0.05
               else "écart distinguable de zéro au seuil de 5 %, sans indication sur son ampleur")
    return f"test des signes bilatéral p = {p_value:.2f} ({reading})"


def honest_status(record: dict[str, Any] | None, state: Path = STATE, module: str | None = None) -> str | None:
    """Status a stored record may claim today.

    A record stays `reinforced_available` only if it was built from the official
    registry entry AND that entry still names the same run with its adapter on disk.
    Any other record that claims an adapter (including manifests written before this
    rule) is reported as `candidate_not_promoted`. Other statuses are returned unchanged.
    """
    if not isinstance(record, dict):
        return None
    status = record.get("status")
    if status not in {PROMOTED_STATUS, CANDIDATE_STATUS}:
        return status
    module = module or record.get("module")
    if status == PROMOTED_STATUS and record.get("promoted_officially") is True and record.get("run_id") and module:
        official = read_json(Path(state) / "registry" / f"{module}.json")
        if (isinstance(official, dict) and official.get("run_id") == record["run_id"]
                and Path(str(official.get("adapter") or "")).is_file()):
            return PROMOTED_STATUS
    return CANDIDATE_STATUS


ALL_UI_MODULES: dict[str, dict[str, str]] = {
    "3d": {
        "label": "3D · Géométrie Pure, Rigging UniRig & Assemblage",
        "base_model": "microsoft/TRELLIS.2-4B + VAST-AI/UniRig + tencent/HY-Motion-1.0 (Intouchables)",
        "trainer": "Pareto Flow-Matching DPO + Rectified Velocity Consistency + Geodesic DQS Auto-Rigging + Replay d'Échecs",
        "dataset_pack": "Pack JeffreyXiang/TRELLIS-500K (504 006 objets 3D : ABO, 3D-FUTURE, HSSD, Toys4k, ObjaverseXL) + Articulation/Rigging Benchmarks",
        "axes_cibles": "Précision géométrique, Topologie manifold (0 auto-intersection), Style & Fidélité 360°, Rigging géodésique DQS (0 pli articulaire) & Cinématique IK sans glissement",
    },
    "image": {
        "label": "Image · Studio Photoréaliste, Scènes & 16K",
        "base_model": "Comfy-Org/flux2-dev · flux2-dev-Q4_K_M.gguf + mistral_3_small_flux2_fp8 (Intouchable)",
        "trainer": "Active Pairwise Low-Rank Surrogate ES + LoRA GGUF",
        "dataset_pack": "Briefs multi-styles (Photoréaliste, Paysage 8K, Architecture, Anime, Cinéma, Macro PBR)",
        "axes_cibles": "Style & Photoréalisme, Alignement prompt CLIP, Score esthétique LAION, Contraste & Micro-texture sans saturation",
    },
    "code": {
        "label": "Code · Ingénierie Full-Stack, Motion Design & Backend",
        "base_model": "qwen3-coder-next:q4_K_M / Qwen/Qwen3-8B (Intouchable)",
        "trainer": "Oracle Supervised DPO + Sandbox Execution Gate",
        "dataset_pack": "Familles algorithmiques disjointes, cas limites Unicode/décimaux & contrats qualité motion/backend",
        "axes_cibles": "Exactitude d'exécution sandbox, Complexité algorithmique, Qualité Motion Design & Robustesse Backend",
    },
    "cyber": {
        "label": "Cyber · Audit Offensif/Défensif & Remédiation",
        "base_model": "qwen-cyber:latest / Qwen/Qwen3-8B (Intouchable)",
        "trainer": "Sandboxed Agent Preference DPO",
        "dataset_pack": "Simulations de sécurité isolées, permissions POSIX, réseaux IPv4/IPv6 & remédiation",
        "axes_cibles": "Précision des correctifs, Zéro effet de bord hôte, Détection de vulnérabilités & Validation sandbox",
    },
    "conversation": {
        "label": "Conversation · Raisonnement Multimodal & Synthèse",
        "base_model": "qwen3-vl:30b / Qwen/Qwen3-8B (Intouchable)",
        "trainer": "Structured Oracle DPO",
        "dataset_pack": "Raisonnement multi-entrées avec vérification exacte et cohérence factuelle",
        "axes_cibles": "Justesse logique, Respect strict des contraintes, Clarté & Absence d'hallucination",
    },
    "cowork": {
        "label": "Cowork · Orchestration Multi-Outils & Missions",
        "base_model": "qwen3-coder-next:q4_K_M / Qwen/Qwen3-8B (Intouchable)",
        "trainer": "Sandboxed Multi-Step Agent DPO",
        "dataset_pack": "Plans d'outils multi-étapes avec contrats de complétion vérifiés",
        "axes_cibles": "Fiabilité d'orchestration, Continuité des missions & Livraison vérifiée",
    },
    "learning": {
        "label": "Academy · Pédagogie Progressive & Vérification",
        "base_model": "deepseek-r1:32b / Qwen/Qwen3-8B (Intouchable)",
        "trainer": "Structured Pedagogical Oracle DPO",
        "dataset_pack": "Exercices progressifs avec contre-exemples et vérification croisée",
        "axes_cibles": "Précision mathématique/scientifique, Clarté pédagogique & Auto-vérification",
    },
    "business": {
        "label": "Business · Intelligence Stratégique & Copilote",
        "base_model": "qwen3-vl:30b + deepseek-r1:32b (Intouchable)",
        "trainer": "Structured Financial & Strategic Preference Alignment",
        "dataset_pack": "Études de marché, modélisation financière & arbitrage stratégique",
        "axes_cibles": "Précision analytique, Pertinence métier & Structuration exécutive",
    },
    "drawing": {
        "label": "Drawing · Croquis, Storyboard & Illustration",
        "base_model": "qwen3-vl:30b + flux2-dev-Q4_K_M.gguf (Intouchable)",
        "trainer": "Pairwise Linework & Style Consistency Alignment",
        "dataset_pack": "Croquis préparatoires, encrage manga/comics & cohérence de trait",
        "axes_cibles": "Propreté du trait, Cohérence anatomique & Fidélité de style",
    },
    "audio": {
        "label": "Voix · Synthèse Kokoro & Prosodie Française",
        "base_model": "hexgrad/Kokoro-82M + faster-whisper-large-v3 (Intouchable)",
        "trainer": "Measured Evolution with Whisper ASR Gate",
        "dataset_pack": "Cas phonétiques français difficiles, liaisons, homophones & 6 cibles prosodiques",
        "axes_cibles": "Intelligibilité (WER minimal), Prosodie naturelle, Zéro saturation (clipping) & Dynamique",
    },
    "video": {
        "label": "Vidéo · Cinéma Temporel Wan2.2 5B",
        "base_model": "Wan-AI/Wan2.2-TI2V-5B (Intouchable)",
        "trainer": "Active Temporal Surrogate ES",
        "dataset_pack": "Briefs temporels de mouvement, permanence d'objet et continuité optique",
        "axes_cibles": "Continuité optique inter-trames, Stabilité d'identité, Alignement CLIP & Anti-scintillement",
    },
    "animation": {
        "label": "Animation & Rigging · UniRig + HY-Motion-1.0 + Foot-Lock IK",
        "base_model": "VAST-AI/UniRig + tencent/HY-Motion-1.0 (Intouchables)",
        "trainer": "Active Kinematic Surrogate ES + Dual-Quaternion Geodesic Skinning Calibration",
        "dataset_pack": "Familles d'actions locomotrices, rigging squelettique auto-régressif et cinématique inverse sans glissement",
        "axes_cibles": "Précision Skinning Géodésique DQS, Stabilité de longueur d'os, Contacts au sol Foot-Lock IK (0 glissement), Fluidité (jerk minimal)",
    },
}


def link_trellis_500k_pack() -> dict[str, Any]:
    """Relie le pack officiel JeffreyXiang/TRELLIS-500K (504 006 objets 3D) dans modele/renforce/3d/datasets/."""
    pack_dir = RENFORCE_ROOT / "3d" / "datasets" / "TRELLIS-500K"
    pack_dir.mkdir(parents=True, exist_ok=True)
    csv_files = (
        "Toys4k.csv",
        "ABO.csv",
        "3D-FUTURE.csv",
        "HSSD.csv",
        "ObjaverseXL_sketchfab.csv",
        "ObjaverseXL_github.csv",
    )
    linked: dict[str, int] = {}
    try:
        from huggingface_hub import hf_hub_download
        for name in csv_files:
            try:
                cached = Path(hf_hub_download("JeffreyXiang/TRELLIS-500K", name, repo_type="dataset", local_files_only=True))
                dest = pack_dir / name
                if not dest.exists() and cached.is_file():
                    os.symlink(cached.resolve(), dest)
                if dest.exists():
                    with dest.open(encoding="utf-8", errors="ignore") as f:
                        linked[name] = max(0, sum(1 for _ in f) - 1)
            except Exception:
                continue
    except Exception:
        pass
    summary = {
        "dataset_repo": "JeffreyXiang/TRELLIS-500K",
        "total_objects": sum(linked.values()),
        "subsets": linked,
        "local_path": str(pack_dir),
    }
    atomic_json(pack_dir / "pack_manifest.json", summary)
    return summary


def _extract_overnight_3d_cycles(state: Path) -> list[dict[str, Any]]:
    """Extrait tous les cycles nocturnes complets (Kaggle Dual-T4 + Audit 96 maillages RTX 5070 Ti)."""
    # Titles carry no figures: the measured values are printed from each report.
    known_titles = {
        "3d-20261017-024739-f029e5": (
            "Cycle Nocturne #1 — Topologie BVH",
            "adapter_nocturne_c1_topologie_bvh.safetensors",
        ),
        "3d-20261017-054241-c9cbb2": (
            "Cycle Nocturne #2 — Photoréalisme, Low-Poly & Organique",
            "adapter_nocturne_c2_photoreal_lowpoly.safetensors",
        ),
    }
    cycles: list[dict[str, Any]] = []
    runs_root = state / "runs"
    if not runs_root.is_dir():
        return cycles
    for run_dir in sorted(runs_root.glob("3d-*")):
        run_id = run_dir.name
        if run_id in {"3d-20260927-102144-15d62f", "3d-20260927-204337-c4d5d2"}:
            continue
        rep_path = run_dir / "report.json"
        cand_path = run_dir / "candidate.safetensors"
        if rep_path.is_file() and cand_path.is_file():
            rep = read_json(rep_path, {})
            if rep.get("base") and rep.get("candidate") and len(rep["base"]) == len(rep["candidate"]):
                rec = _build_3d_record_from_report(
                    run_id,
                    cand_path,
                    rep,
                    "candidate",
                    promoted=False,
                    audit_source_run=run_id,
                )
                default_idx = len(cycles) + 1
                title, target_filename = known_titles.get(
                    run_id,
                    (
                        f"Cycle Nocturne #{default_idx} ({run_id}) — Écart vs base {rec['gain_points_100']:+.3f} pt",
                        f"adapter_nocturne_c{default_idx}_{run_id[-6:]}.safetensors",
                    ),
                )
                rec["title"] = title
                rec["target_filename"] = target_filename
                cycles.append(rec)
    return cycles


def _extract_3d_verified_record(state: Path) -> dict[str, Any] | None:
    """Return the 3D record published under `modele/renforce/3d/`.

    - The adapter listed in the official registry (promotion gate passed) is always kept and is
      the only one labelled `reinforced_available`.
    - Otherwise the best audited candidate is published with its measurements as
      `candidate_not_promoted`: it is neither "verified" nor served by default.
    - `before_after_comparison` only carries measured values.
    """
    candidates_pool: list[dict[str, Any]] = []

    # 1. Candidat officiel du registre s'il existe
    reg = read_json(state / "registry" / "3d.json")
    if reg and Path(reg.get("adapter", "")).is_file():
        run_dir = state / "runs" / reg["run_id"]
        report = read_json(run_dir / "report.json", {})
        if report.get("base") and report.get("candidate"):
            candidates_pool.append(
                _build_3d_record_from_report(reg["run_id"], Path(reg["adapter"]), report, "candidate", promoted=True)
            )

    # 2. Historical candidate audited in a separate run (3d-20260927-102144-15d62f); never promoted here
    audit_run = state / "runs" / "3d-20260927-204337-c4d5d2"
    parent_run = state / "runs" / "3d-20260927-102144-15d62f"
    if (audit_run / "report.json").is_file() and (parent_run / "candidate.safetensors").is_file():
        report = read_json(audit_run / "report.json", {})
        if report.get("base") and report.get("parent") and len(report["base"]) == len(report["parent"]):
            candidates_pool.append(
                _build_3d_record_from_report(
                    "3d-20260927-102144-15d62f",
                    parent_run / "candidate.safetensors",
                    report,
                    "parent",
                    promoted=False,
                    audit_source_run="3d-20260927-204337-c4d5d2",
                )
            )

    # 3. Tous les cycles nocturnes audités
    overnight_cycles = _extract_overnight_3d_cycles(state)
    for oc in overnight_cycles:
        candidates_pool.append(dict(oc))

    # A promoted adapter is always kept; an unpromoted candidate must at least beat the base in audit.
    valid_champions = [
        c for c in candidates_pool
        if c.get("promoted_officially") is True or c.get("score_renforce_100", 0.0) > c.get("score_base_100", 0.0)
    ]
    if not valid_champions:
        return None

    # The official registry wins; only then the best audited score.
    valid_champions.sort(
        key=lambda r: (r.get("promoted_officially") is True, float(r.get("score_renforce_100", 0.0))), reverse=True
    )
    best = dict(valid_champions[0])
    promoted = best.get("promoted_officially") is True
    runner_up = valid_champions[1] if len(valid_champions) > 1 else None
    latest_cycle = overnight_cycles[-1] if overnight_cycles else best

    measured = (
        f"{best['run_id']} : {best['score_renforce_100']:.3f}/100 contre {best['score_base_100']:.3f}/100 pour la base, "
        f"sur {best['samples_audited']} échantillons appariés"
    )
    best["overnight_cycles"] = overnight_cycles
    best["champion_selection_policy"] = {
        "rule": "STRICT_MAX_HOLDOUT_CHAMPION" if promoted else "BEST_MEASURED_CANDIDATE_NOT_PROMOTED",
        "base_model_untouchable": True,
        "explanation": (
            f"Adaptateur inscrit au registre officiel après la porte de promotion ({measured})."
            if promoted else
            f"Aucun adaptateur promu. Meilleur candidat mesuré en audit ({measured}) : il n'a pas franchi la porte "
            "de promotion, le modèle de base reste servi."
        ),
        "candidates_evaluated": len(candidates_pool),
        "champion_run_id": best["run_id"],
        "latest_cycle_run_id": latest_cycle.get("run_id"),
        "latest_cycle_promoted": promoted and latest_cycle.get("run_id") == best["run_id"],
    }
    # No rigging evaluation exists in this pipeline: the stack is described, never scored.
    # The metric keys are kept for readers of the manifest, with an explicit "not measured".
    unmeasured = {"before_base": None, "after_reinforced": None, "delta": None, "measured": False}
    best["rigging_and_animation_stack"] = {
        "measured": False,
        "note": "Étape du pipeline décrite, pas un gain mesuré : aucune évaluation de rigging n'est exécutée.",
        "skeleton_autorigger": "VAST-AI/UniRig (SIGGRAPH 2025 Autoregressive Skeleton Tree) + Blender 5.1 Rigify",
        "skinning_solver": "Geodesic Heat-Diffusion + Dual-Quaternion Skinning (DQS)",
        "motion_generator": "tencent/HY-Motion-1.0 + Foot-Lock IK",
        "metrics_before_after": {
            "geodesic_skinning_accuracy_100": dict(unmeasured),
            "joint_volume_preservation_pct": dict(unmeasured),
            "foot_sliding_error_mm": dict(unmeasured),
            "kinematic_smoothness_100": dict(unmeasured),
        },
    }
    best["before_after_comparison"] = {
        "base_untouchable": {
            "label": "Modèle de Base Intouchable (TRELLIS.2-4B)",
            "score_100": best["score_base_100"],
            "clip_mean_100": best["axes_gains"]["style_et_fidelite_multi_vues_clip"]["base"],
            "worst_view_360_100": best["axes_gains"]["coherence_360_pire_vue"]["base"],
            "self_intersections": best["axes_gains"]["reduction_auto_intersections"]["base"],
        },
        "previous_or_challenger": {
            "label": f"Challenger / Cycle Précédent ({(runner_up or latest_cycle)['run_id']})",
            "score_100": (runner_up or latest_cycle)["score_renforce_100"],
            "clip_mean_100": (runner_up or latest_cycle)["axes_gains"]["style_et_fidelite_multi_vues_clip"]["renforce"],
            "worst_view_360_100": (runner_up or latest_cycle)["axes_gains"]["coherence_360_pire_vue"]["renforce"],
            "self_intersections": (runner_up or latest_cycle)["axes_gains"]["reduction_auto_intersections"]["renforce"],
        },
        # Key name kept for readers of the manifest; the label states the real status.
        "active_champion": {
            "label": f"{'Modèle renforcé promu' if promoted else 'Candidat non promu'} ({best['run_id']})",
            "score_100": best["score_renforce_100"],
            "gain_vs_base_pts": best["gain_points_100"],
            "gain_vs_challenger_pts": _delta(best["score_renforce_100"], (runner_up or latest_cycle)["score_renforce_100"], 1, 4),
            "clip_mean_100": best["axes_gains"]["style_et_fidelite_multi_vues_clip"]["renforce"],
            "worst_view_360_100": best["axes_gains"]["coherence_360_pire_vue"]["renforce"],
            "self_intersections": best["axes_gains"]["reduction_auto_intersections"]["renforce"],
        },
    }
    return best


def _build_3d_record_from_report(
    run_id: str,
    adapter_path: Path,
    report: dict[str, Any],
    branch_key: str,
    *,
    promoted: bool,
    audit_source_run: str | None = None,
) -> dict[str, Any]:
    base_rows = report.get("base", [])
    comp_rows = report.get(branch_key, [])
    b_scores = [float(r["judge"]["score"]) for r in base_rows]
    c_scores = [float(r["judge"]["score"]) for r in comp_rows]
    deltas = [c - b for c, b in zip(c_scores, b_scores)]
    wins = sum(1 for d in deltas if d > 1e-9)
    losses = sum(1 for d in deltas if d < -1e-9)
    ties = len(deltas) - wins - losses

    def _m_avg(rows: list[dict], key: str) -> float | None:
        # None, not 0.0, when no row carries the metric: an absent measure is not a zero.
        vals = [float(r["judge"]["metrics"][key]) for r in rows if isinstance(r.get("judge", {}).get("metrics", {}).get(key), (int, float))]
        return statistics.mean(vals) if vals else None

    b_clip = _m_avg(base_rows, "clip_mean")
    c_clip = _m_avg(comp_rows, "clip_mean")
    b_worst = _m_avg(base_rows, "clip_worst_view")
    c_worst = _m_avg(comp_rows, "clip_worst_view")
    b_inter = _m_avg(base_rows, "self_intersections")
    c_inter = _m_avg(comp_rows, "self_intersections")
    b_nonm = _m_avg(base_rows, "nonmanifold_edge_fraction")
    c_nonm = _m_avg(comp_rows, "nonmanifold_edge_fraction")
    b_degen = _m_avg(base_rows, "degenerate_face_fraction")
    c_degen = _m_avg(comp_rows, "degenerate_face_fraction")
    b_frag = _m_avg(base_rows, "fragment_area_fraction")
    c_frag = _m_avg(comp_rows, "fragment_area_fraction")

    # Gains par famille de sujet et par style visuel
    by_style: dict[str, list[float]] = {}
    by_family: dict[str, list[float]] = {}
    for r_b, r_c in zip(base_rows, comp_rows):
        d = (float(r_c["judge"]["score"]) - float(r_b["judge"]["score"])) * 100.0
        st = r_c.get("style") or "standard"
        fam = r_c.get("family") or "objet"
        by_style.setdefault(st, []).append(d)
        by_family.setdefault(fam, []).append(d)

    run_dir = STATE / "runs" / run_id
    t_metrics = read_json(run_dir / "training_metrics.json", {})
    config = read_json(run_dir / "config.json", defaults("3d"))
    base_manifest = read_json(run_dir / "base_manifest.json", {})
    initial_loss = _num(t_metrics.get("initial_validation_loss"))
    best_loss = _num(t_metrics.get("best_validation_loss"))

    def _ecart(delta: float | None, spec: str, unit: str) -> str:
        return NON_MESURE if delta is None else f"Écart mesuré : {delta:{spec}} {unit}"

    return {
        "schema": 1,
        "module": "3d",
        "version": 1,
        "name": f"Aurora-3D-TRELLIS2-Renforce-v1 ({run_id})",
        "run_id": run_id,
        "audit_run_id": audit_source_run or report.get("run_id") or run_id,
        "promoted_officially": promoted,
        # Only a record built from the official registry entry may claim availability.
        "status": PROMOTED_STATUS if promoted else CANDIDATE_STATUS,
        "measured": True,
        "base_model": config.get("models", {}).get("3d", "microsoft/TRELLIS.2-4B"),
        "base_fingerprint": report.get("base_fingerprint"),
        "source_adapter": str(adapter_path.resolve()),
        "sha256": file_hash(adapter_path),
        "score_base_100": round(statistics.mean(b_scores) * 100, 4),
        "score_renforce_100": round(statistics.mean(c_scores) * 100, 4),
        "gain_points_100": round(statistics.mean(deltas) * 100, 4),
        "relative_gain_percent": round((statistics.mean(deltas) / max(statistics.mean(b_scores), 1e-9)) * 100, 2),
        "samples_audited": len(deltas),
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "win_rate_percent": round(100.0 * wins / max(1, len(deltas)), 1),
        "sign_test_p_two_sided": sign_test_two_sided(wins, losses),
        "epochs": t_metrics.get("epochs"),
        # Verdicts restate the measured difference, whatever its sign; None means not measured.
        "axes_gains": {
            "style_et_fidelite_multi_vues_clip": {
                "label": "Style & Fidélité Multi-Vues (CLIP moyen)",
                "base": _scaled(b_clip, 100, 3),
                "renforce": _scaled(c_clip, 100, 3),
                "delta_pts": _delta(c_clip, b_clip, 100, 3),
                "direction": "higher_is_better",
                "verdict": _ecart(_delta(c_clip, b_clip, 100, 3), "+.3f", "pt"),
            },
            "coherence_360_pire_vue": {
                "label": "Précision Face Arrière / Pire Vue 360° (CLIP worst-view)",
                "base": _scaled(b_worst, 100, 3),
                "renforce": _scaled(c_worst, 100, 3),
                "delta_pts": _delta(c_worst, b_worst, 100, 3),
                "direction": "higher_is_better",
                "verdict": _ecart(_delta(c_worst, b_worst, 100, 3), "+.3f", "pt sur la pire vue"),
            },
            "reduction_auto_intersections": {
                "label": "Propreté Géométrique & Auto-Intersections (moins = mieux)",
                "base": _scaled(b_inter, 1, 1),
                "renforce": _scaled(c_inter, 1, 1),
                "delta_intersections": _delta(c_inter, b_inter, 1, 1),
                "direction": "lower_is_better",
                "verdict": _ecart(_delta(c_inter, b_inter, 1, 1), "+.1f", "auto-intersections par maillage"),
            },
            "topologie_manifold_et_faces": {
                "label": "Topologie Manifold & Faces Dégénérées",
                "base_nonmanifold_pct": _scaled(b_nonm, 100, 4),
                "renforce_nonmanifold_pct": _scaled(c_nonm, 100, 4),
                "base_degenerate_pct": _scaled(b_degen, 100, 5),
                "renforce_degenerate_pct": _scaled(c_degen, 100, 5),
                "delta_degenerate_pct": _delta(c_degen, b_degen, 100, 5),
                "base_fragment_pct": _scaled(b_frag, 100, 2),
                "renforce_fragment_pct": _scaled(c_frag, 100, 2),
                "verdict": _ecart(_delta(c_degen, b_degen, 100, 5), "+.5f", "pt de faces dégénérées"),
            },
            "loss_flow_matching_dpo": {
                "label": "Convergence Flow-Matching DPO (SparseStructureFlowModel 1.3B)",
                "initial_val_loss": None if initial_loss is None else round(initial_loss, 5),
                "best_val_loss": None if best_loss is None else round(best_loss, 5),
                "measured": initial_loss is not None and best_loss is not None,
                "verdict": (
                    "Perte de validation relevée à l'entraînement ; une baisse de perte n'est pas un gain de qualité démontré"
                    if initial_loss is not None and best_loss is not None else NON_MESURE
                ),
            },
        },
        "gains_by_style_pts": {k: round(statistics.mean(v), 3) for k, v in sorted(by_style.items())},
        "gains_by_family_pts": {k: round(statistics.mean(v), 3) for k, v in sorted(by_family.items())},
        "config": config,
        "base_manifest_count": len(base_manifest),
        "updated_at": time.time(),
    }


def sync_all_reinforced_models(state: Path = STATE) -> dict[str, Any]:
    """Synchronise `modele/renforce/<module>/` et régénère tous les fichiers `GAINS.md`."""
    state = Path(state).resolve()
    RENFORCE_ROOT.mkdir(parents=True, exist_ok=True)
    trellis_pack = link_trellis_500k_pack()

    modules_summary: dict[str, dict[str, Any]] = {}
    for mod, meta in ALL_UI_MODULES.items():
        mod_dir = RENFORCE_ROOT / mod
        mod_dir.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] | None = None

        if mod == "3d":
            record = _extract_3d_verified_record(state)
            if record and Path(record["source_adapter"]).is_file():
                dest_adapter = mod_dir / "adapter.safetensors"
                shutil.copy2(record["source_adapter"], dest_adapter)
                record["adapter"] = str(dest_adapter.resolve())
                # Copie également les adaptateurs des cycles nocturnes dans modele/renforce/3d/
                for oc in record.get("overnight_cycles", []):
                    src_oc = Path(oc.get("source_adapter", ""))
                    if src_oc.is_file() and oc.get("target_filename"):
                        dst_oc = mod_dir / oc["target_filename"]
                        shutil.copy2(src_oc, dst_oc)
                        oc["adapter"] = str(dst_oc.resolve())
                atomic_json(mod_dir / "manifest.json", record)
        else:
            reg = read_json(state / "registry" / f"{mod}.json")
            if reg and Path(reg.get("adapter", "")).is_file():
                dest_adapter = mod_dir / "adapter.safetensors"
                shutil.copy2(reg["adapter"], dest_adapter)
                run_dir = state / "runs" / reg["run_id"]
                rep = read_json(run_dir / "report.json", {})
                gate = rep.get("gate", {})
                record = {
                    "schema": 1,
                    "module": mod,
                    "version": reg.get("version", 1),
                    "name": reg.get("name", f"Aurora-{mod}-Renforce-v1"),
                    "run_id": reg["run_id"],
                    "promoted_officially": True,
                    "status": PROMOTED_STATUS,
                    "base_model": meta["base_model"],
                    "adapter": str(dest_adapter.resolve()),
                    "sha256": reg["sha256"],
                    # Values absent from the audit gate stay None instead of a 0.0 placeholder.
                    "score_base_100": _scaled(gate.get("base_mean"), 100, 4),
                    "score_renforce_100": _scaled(gate.get("candidate_mean", reg.get("score")), 100, 4),
                    "gain_points_100": _scaled(gate.get("base_gain_points", gate.get("gain_points")), 1, 4),
                    "samples_audited": _count(gate.get("samples")),
                    "wins": _count(gate.get("wins")),
                    "ties": _count(gate.get("ties")),
                    "losses": _count(gate.get("losses")),
                    "updated_at": reg.get("promoted_at", time.time()),
                }
                record["measured"] = record["score_base_100"] is not None and record["score_renforce_100"] is not None
                atomic_json(mod_dir / "manifest.json", record)
            elif (mod_dir / "manifest.json").is_file():
                record = read_json(mod_dir / "manifest.json")
                # Reached only without a usable official registry entry: such a manifest
                # cannot claim a promotion. The file itself is left untouched on disk.
                if isinstance(record, dict) and record.get("status") in {PROMOTED_STATUS, CANDIDATE_STATUS}:
                    record = {**record, "status": CANDIDATE_STATUS, "promoted_officially": False}
                elif isinstance(record, dict) and record.get("status") == "base_only_ready_for_training":
                    # Our own placeholder: rewrite it below, so one written with a 0.0 gain
                    # is replaced by the current "not measured" fields.
                    record = None

        if not record:
            record = {
                "schema": 1,
                "module": mod,
                "version": 0,
                "name": f"En attente de cycle d'entraînement ({mod})",
                "run_id": None,
                "promoted_officially": False,
                "status": "base_only_ready_for_training",
                "measured": False,
                "base_model": meta["base_model"],
                "adapter": None,
                "sha256": None,
                "score_base_100": None,
                "score_renforce_100": None,
                # No audit ran for this module: the gain is unknown, not zero.
                "gain_points_100": None,
                "samples_audited": 0,
                "updated_at": time.time(),
            }
            atomic_json(mod_dir / "manifest.json", record)

        _write_module_gains_md(mod_dir / "GAINS.md", mod, meta, record, trellis_pack if mod == "3d" else None)
        modules_summary[mod] = {**meta, **record, "gains_md": f"modele/renforce/{mod}/GAINS.md"}

    _write_master_gains_md(RENFORCE_ROOT / "GAINS_MODELES_RENFORCES.md", modules_summary, trellis_pack)
    before_after_summary: dict[str, Any] = {}
    try:
        from .before_after_report import generate_before_after_visual_and_report
        before_after_summary = generate_before_after_visual_and_report(state)
    except Exception:
        pass
    return {
        "renforce_root": str(RENFORCE_ROOT),
        "master_markdown": str(RENFORCE_ROOT / "GAINS_MODELES_RENFORCES.md"),
        "before_after_report": before_after_summary,
        "trellis_500k_pack": trellis_pack,
        "modules": modules_summary,
    }


def _write_module_gains_md(
    path: Path,
    mod: str,
    meta: dict[str, str],
    record: dict[str, Any],
    trellis_pack: dict[str, Any] | None = None,
) -> None:
    # The caller passes a record whose status was already checked against the official registry.
    promoted = record.get("status") == PROMOTED_STATUS and record.get("promoted_officially") is True
    has_gain = promoted or record.get("status") == CANDIDATE_STATUS
    role = "Modèle renforcé promu" if promoted else "Candidat non promu"
    # Figures computed by this module from an audit report carry `measured: True`; a manifest
    # written elsewhere is only quoted, never presented as a measurement of ours.
    origin = "mesures d'audit" if record.get("measured") is True else "valeurs du manifeste, non revérifiées"
    if promoted:
        status_label = "✅ **Modèle renforcé promu** (porte de promotion franchie, inscrit au registre officiel)"
    elif has_gain:
        status_label = (f"🧪 **Candidat non promu** (ci-dessous : {origin} ; la porte de promotion n'a pas été "
                        "franchie, le modèle de base reste servi)")
    else:
        status_label = "⏳ **Modèle de base actif** (aucun candidat mesuré : gains non mesurés)"
    samples = _fmt(record.get("samples_audited"), ".0f")
    lines = [
        f"# 🛡️ Bilan du Modèle Renforcé — {meta['label']} (`{mod}`)",
        "",
        f"- **Modèle de Base (Intouchable)** : `{meta['base_model']}`",
        f"- **Dossier Modèle Renforcé** : `modele/renforce/{mod}/`",
        f"- **Algorithme d'Entraînement** : `{meta['trainer']}`",
        f"- **Pack de Données / Curriculum** : {meta['dataset_pack']}",
        f"- **Axes de Qualité Ciblés** : {meta['axes_cibles']}",
        f"- **Statut Actuel** : {status_label}",
        "",
    ]
    if has_gain:
        sign_test = sign_test_sentence(record.get("wins"), record.get("losses"))
        relative = record.get("relative_gain_percent")
        relative_txt = f" (`{_fmt(relative, '+.2f', ' %')}`)" if _num(relative) is not None else ""
        if _num(record.get("wins")) is None or _num(record.get("losses")) is None:
            pairing = f"victoires / défaites : {NON_MESURE}"
        else:
            pairing = (f"{_fmt(record.get('wins'), '.0f')} victoires / {_fmt(record.get('losses'), '.0f')} défaites "
                       f"sur {samples} générations appariées" + (f" · {sign_test}" if sign_test else ""))
        lines.extend([
            f"## 📊 1. {role} (`adapter.safetensors`) comparé à la base intouchable — {origin}",
            "",
            f"| Métrique / Axe d'Évaluation | Modèle de Base (Intouchable) | {role} (`adapter.safetensors`) | Écart mesuré | Lecture |",
            "| :--- | :---: | :---: | :---: | :--- |",
            f"| **Score Global Composite (/100)** | `{_fmt(record.get('score_base_100'))}` | **`{_fmt(record.get('score_renforce_100'))}`** | **`{_fmt(record.get('gain_points_100'), '+.3f', ' pts')}`**{relative_txt} | {pairing} |",
        ])
        axes = record.get("axes_gains", {})
        if axes:
            if "style_et_fidelite_multi_vues_clip" in axes:
                a = axes["style_et_fidelite_multi_vues_clip"]
                lines.append(f"| **{a['label']}** | `{_fmt(a.get('base'))}` | **`{_fmt(a.get('renforce'))}`** | **`{_fmt(a.get('delta_pts'), '+.3f', ' pt')}`** | {a['verdict']} |")
            if "coherence_360_pire_vue" in axes:
                a = axes["coherence_360_pire_vue"]
                lines.append(f"| **{a['label']}** | `{_fmt(a.get('base'))}` | **`{_fmt(a.get('renforce'))}`** | **`{_fmt(a.get('delta_pts'), '+.3f', ' pt')}`** | {a['verdict']} |")
            if "reduction_auto_intersections" in axes:
                a = axes["reduction_auto_intersections"]
                lines.append(f"| **{a['label']}** | `{_fmt(a.get('base'), '.1f')}` | **`{_fmt(a.get('renforce'), '.1f')}`** | **`{_fmt(a.get('delta_intersections'), '+.1f')}`** | {a['verdict']} |")
            if "topologie_manifold_et_faces" in axes:
                a = axes["topologie_manifold_et_faces"]
                lines.append(f"| **{a['label']}** | `{_fmt(a.get('base_degenerate_pct'), '.4f', ' %')}` dégén. | **`{_fmt(a.get('renforce_degenerate_pct'), '.4f', ' %')}` dégén.** | `{_fmt(a.get('delta_degenerate_pct'), '+.5f', ' pt')}` | {a['verdict']} |")
        if record.get("before_after_comparison"):
            ba = record["before_after_comparison"]
            pol = record.get("champion_selection_policy", {})
            base_row, other_row, kept_row = ba["base_untouchable"], ba["previous_or_challenger"], ba["active_champion"]
            lines.extend([
                "### ⚖️ Comparatif Avant / Après & Porte de Promotion",
                f"- **Politique appliquée** : `{pol.get('rule', 'non renseignée')}` — {pol.get('explanation', '')}",
                "",
                "| Phase / Modèle | Score Global (/100) | CLIP Multi-Vues (/100) | Pire Vue 360° (/100) | Auto-Intersections BVH | Statut |",
                "| :--- | :---: | :---: | :---: | :---: | :---: |",
                f"| **1. Avant (Base Intouchable)** | `{_fmt(base_row.get('score_100'), '.4f')}` | `{_fmt(base_row.get('clip_mean_100'))}` | `{_fmt(base_row.get('worst_view_360_100'))}` | `{_fmt(base_row.get('self_intersections'), '.1f')}` | 🛡️ Poids d'origine |",
                f"| **2. {other_row.get('label') or 'Autre cycle mesuré'}** | `{_fmt(other_row.get('score_100'), '.4f')}` | `{_fmt(other_row.get('clip_mean_100'))}` | `{_fmt(other_row.get('worst_view_360_100'))}` | `{_fmt(other_row.get('self_intersections'), '.1f')}` | 📦 Mesuré en audit |",
                f"| **3. Après ({role})** | **`{_fmt(kept_row.get('score_100'), '.4f')}`** (`{_fmt(kept_row.get('gain_vs_base_pts'), '+.4f')}`) | **`{_fmt(kept_row.get('clip_mean_100'))}`** | **`{_fmt(kept_row.get('worst_view_360_100'))}`** | **`{_fmt(kept_row.get('self_intersections'), '.1f')}`** | {'✅ **Promu**' if promoted else '🧪 **Non promu**'} |",
                "",
            ])

        if record.get("rigging_and_animation_stack"):
            rig = record["rigging_and_animation_stack"]
            lines.extend([
                "### 🦴 Pile Rigging & Animation Squelettique 3D (`UniRig` + `DQS` + `HY-Motion-1.0`)",
                f"- **Auto-Rigging Squelettique** : `{rig.get('skeleton_autorigger')}`",
                f"- **Solveur de Skinning** : `{rig.get('skinning_solver')}`",
                f"- **Moteur Cinématique** : `{rig.get('motion_generator')}`",
            ])
            if rig.get("measured") is not True:
                # No rigging evaluation exists yet. The before/after table that stood here
                # was written by hand, so nothing numeric is printed until one is measured.
                lines.append(
                    "- **Mesures avant / après** (précision du skinning, volume articulaire, glissement d'appui, fluidité) : "
                    f"**{NON_MESURE}**. Ces lignes décrivent une étape du pipeline, pas un gain : aucune évaluation de "
                    "rigging n'est exécutée par l'audit."
                )
            lines.append("")

        lines.extend([
            f"### 🔍 Détail des écarts mesurés par style et par famille ({role})",
            "",
        ])
        if record.get("gains_by_style_pts"):
            lines.append(f"#### Par style visuel (écart moyen vs base ; {samples} générations d'audit au total) :")
            for st, val in record["gains_by_style_pts"].items():
                lines.append(f"- **{st}** : `{_fmt(val, '+.3f', ' pts / 100')}`")
            lines.append("")
        if record.get("gains_by_family_pts"):
            lines.append("#### Par famille géométrique (écart moyen vs base, sujets d'audit) :")
            for fam, val in record["gains_by_family_pts"].items():
                lines.append(f"- **{fam}** : `{_fmt(val, '+.3f', ' pts / 100')}`")
            lines.append("")

        overnight_cycles = record.get("overnight_cycles", [])
        if overnight_cycles:
            lines.extend([
                "---",
                "",
                f"## 🌙 2. Cycles nocturnes audités ({len(overnight_cycles)} cycle(s) ; aucun n'est promu par ce tableau)",
                "",
                "| Cycle / Adaptateur Exporté | Score Base (/100) | Score Candidat (/100) | Écart vs Base | Victoires / Défaites (sur n) | Écart CLIP Moyen | Écart Pire Vue 360° | Auto-Intersections BVH | Écarts positifs relevés |",
                "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
            ])
            for oc in overnight_cycles:
                oc_axes = oc.get("axes_gains", {})
                clip_d = oc_axes.get("style_et_fidelite_multi_vues_clip", {}).get("delta_pts")
                worst_d = oc_axes.get("coherence_360_pire_vue", {}).get("delta_pts")
                inter_c = oc_axes.get("reduction_auto_intersections", {}).get("renforce")
                inter_d = oc_axes.get("reduction_auto_intersections", {}).get("delta_intersections")
                st_gains = oc.get("gains_by_style_pts", {})
                fam_gains = oc.get("gains_by_family_pts", {})
                highlights = []
                if _num(inter_d) is not None and inter_d < -50:
                    highlights.append(f"**Auto-intersections `{inter_d:+.1f}`**")
                if st_gains.get("photorealistic", 0) > 0.5:
                    highlights.append(f"**Photoréaliste `{st_gains['photorealistic']:+.3f} pt`**")
                if st_gains.get("low_poly", 0) > 0:
                    highlights.append(f"**Low-Poly `{st_gains['low_poly']:+.3f} pt`**")
                if st_gains.get("clay", 0) > 0.8:
                    highlights.append(f"**Clay `{st_gains['clay']:+.3f} pt`**")
                if fam_gains.get("owl", 0) > 1.0:
                    highlights.append(f"**Owl `{fam_gains['owl']:+.3f} pts`**")
                if fam_gains.get("camera", 0) > 0:
                    highlights.append(f"**Camera `{fam_gains['camera']:+.3f} pt`**")
                lines.append(
                    f"| **`{oc.get('run_id')}`**<br>`{oc.get('target_filename')}` | `{_fmt(oc.get('score_base_100'), '.4f')}` | **`{_fmt(oc.get('score_renforce_100'), '.4f')}`** | **`{_fmt(oc.get('gain_points_100'), '+.4f', ' pt')}`** | **{_fmt(oc.get('wins'), '.0f')} V / {_fmt(oc.get('losses'), '.0f')} D** (n = {_fmt(oc.get('samples_audited'), '.0f')}) | `{_fmt(clip_d, '+.4f', ' pt')}` | **`{_fmt(worst_d, '+.4f', ' pt')}`** | `{_fmt(inter_c, '.1f')}` (`{_fmt(inter_d, '+.1f')}`) | {', '.join(highlights) or oc.get('title', '')} |"
                )
            lines.append("")
            for oc in overnight_cycles:
                oc_samples = _fmt(oc.get("samples_audited"), ".0f")
                lines.extend([
                    f"### 📌 Détail `{oc.get('run_id')}` — {oc.get('title')}",
                    f"- **Fichier exporté dans `modele/renforce/3d/`** : `{oc.get('adapter')}`",
                    f"- **SHA-256** : `{oc.get('sha256')}`",
                    f"- **Écarts par style visuel (vs base, {oc_samples} générations d'audit)** : "
                    + ", ".join(f"`{k}`: **{v:+.3f} pt**" for k, v in oc.get("gains_by_style_pts", {}).items()),
                    f"- **Écarts par famille géométrique (vs base, {oc_samples} générations d'audit)** : "
                    + ", ".join(f"`{k}`: **{v:+.3f} pt**" for k, v in oc.get("gains_by_family_pts", {}).items()),
                    "",
                ])

        base_files = record.get("base_manifest_count")
        lines.extend([
            "### 🔐 Traçabilité & Intégrité Cryptographique",
            f"- **Identifiant du cycle ({role})** : `{record.get('run_id')}`"
            + (f" (audité dans `{record['audit_run_id']}`)" if record.get("audit_run_id") else ""),
            f"- **Fichier d'adaptateur principal** : `{record.get('adapter')}`",
            f"- **SHA-256 de l'adaptateur principal** : `{record.get('sha256')}`",
            f"- **Empreinte du modèle de base** : `{record.get('base_fingerprint')}` "
            f"(fichiers de base recensés pour ce cycle : {_fmt(base_files, '.0f')})",
            "",
        ])
    if trellis_pack:
        lines.extend([
            "## 📦 Pack d'Entraînement 500K+ Rattaché (`TRELLIS-500K`)",
            f"- **Source** : `{trellis_pack['dataset_repo']}` ({trellis_pack['total_objects']:,} objets 3D qualifiés)",
            f"- **Chemin local** : `{trellis_pack['local_path']}`",
            "- **Sous-ensembles actifs** :",
        ])
        for k, v in trellis_pack.get("subsets", {}).items():
            lines.append(f"  - `{k}` : **{v:,}** objets 3D avec captions structurelles multi-niveaux et score esthétique")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _audit_summary(rec: dict[str, Any]) -> str:
    """One French line built only from the fields measured for this record."""
    axes = rec.get("axes_gains") or {}
    parts = [
        f"**`{_fmt(rec.get('gain_points_100'), '+.4f', ' pt')}`** sur 100 "
        f"(`{_fmt(rec.get('score_renforce_100'), '.4f')}` contre `{_fmt(rec.get('score_base_100'), '.4f')}` pour la base)",
        f"{_fmt(rec.get('wins'), '.0f')} victoires / {_fmt(rec.get('losses'), '.0f')} défaites / "
        f"{_fmt(rec.get('ties'), '.0f')} égalités sur {_fmt(rec.get('samples_audited'), '.0f')} générations appariées",
    ]
    sign_test = sign_test_sentence(rec.get("wins"), rec.get("losses"))
    if sign_test:
        parts.append(sign_test)
    parts.extend([
        f"CLIP moyen `{_fmt((axes.get('style_et_fidelite_multi_vues_clip') or {}).get('delta_pts'), '+.4f', ' pt')}`",
        f"pire vue 360° `{_fmt((axes.get('coherence_360_pire_vue') or {}).get('delta_pts'), '+.4f', ' pt')}`",
        f"auto-intersections `{_fmt((axes.get('reduction_auto_intersections') or {}).get('delta_intersections'), '+.1f')}` par maillage",
    ])
    return " ; ".join(parts)


def _write_master_gains_md(path: Path, modules_summary: dict[str, dict[str, Any]], trellis_pack: dict[str, Any]) -> None:
    lines = [
        "# 🏆 Registre Maître des Modèles Renforcés (`modele/renforce/`)",
        "",
        "> **Règle d'Or AuroraIA** : Le **Modèle de Base** de chaque module n'est jamais modifié par l'entraînement. Les adaptateurs entraînés sont rangés dans `/home/juan/AuroraIA/modele/renforce/<module>/`. Seul un adaptateur **promu** (porte de promotion franchie, inscrit au registre officiel) peut être sélectionné comme **Modèle Renforcé** ; un **candidat non promu** reste affiché avec ses mesures d'audit mais le modèle de base continue d'être servi.",
        "",
        "## 📋 Tableau Récapitulatif de Tous les Modules (Base Intouchable vs Modèle Renforcé)",
        "",
        "| Module | Modèle de Base (Intouchable) | Statut | Score Base (/100) | Score Candidat (/100) | Écart mesuré | Axes ciblés (objectifs, pas des gains mesurés) | Fiche `.md` |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |",
    ]
    for mod, info in modules_summary.items():
        promoted = info.get("status") == PROMOTED_STATUS and info.get("promoted_officially") is True
        has_gain = promoted or info.get("status") == CANDIDATE_STATUS
        status_badge = "✅ **Promu**" if promoted else "🧪 Candidat non promu" if has_gain else "🛡️ Base seule (aucun candidat mesuré)"
        sb = f"`{_fmt(info.get('score_base_100'), '.2f')}`"
        sr = f"**`{_fmt(info.get('score_renforce_100'), '.2f')}`**"
        gp = f"**`{_fmt(info.get('gain_points_100'), '+.3f', ' pts')}`**" if has_gain else NON_MESURE
        if has_gain and info.get("measured") is not True and _num(info.get("gain_points_100")) is not None:
            # Quoted from a manifest this module did not compute from an audit report.
            gp += " (valeur du manifeste, non revérifiée)"
        lines.append(
            f"| **{info['label']}** (`{mod}`) | `{info['base_model']}` | {status_badge} | {sb} | {sr} | {gp} | {info['axes_cibles']} | [`{mod}/GAINS.md`]({mod}/GAINS.md) |"
        )

    # Every figure of the 3D focus is read from the records synchronised above.
    three_d = modules_summary.get("3d") or {}
    measured_3d: list[tuple[Any, str, dict[str, Any]]] = []
    if three_d.get("status") in {PROMOTED_STATUS, CANDIDATE_STATUS} and three_d.get("run_id"):
        promoted_3d = three_d.get("status") == PROMOTED_STATUS and three_d.get("promoted_officially") is True
        measured_3d.append(("adapter.safetensors", "promu" if promoted_3d else "candidat non promu", three_d))
    for oc in three_d.get("overnight_cycles") or []:
        # The published adapter is often one of these cycles: do not list its audit twice.
        if not measured_3d or oc.get("run_id") != three_d.get("run_id"):
            measured_3d.append((oc.get("target_filename"), "cycle nocturne, non promu", oc))
    lines.extend([
        "",
        "---",
        "",
        "## 🧊 Focus Module 3D (`microsoft/TRELLIS.2-4B` $\\rightarrow$ `modele/renforce/3d/`)",
        "",
        f"### 1. Synthèse des adaptateurs 3D mesurés en audit ({len(measured_3d)} enregistrement(s))",
    ])
    if not measured_3d:
        lines.append(f"- Aucun adaptateur 3D audité : gains {NON_MESURE}s.")
    for filename, role, rec in measured_3d:
        lines.append(f"- **`{filename}`** (`{rec.get('run_id')}`, {role}) : {_audit_summary(rec)}.")
    lines.extend([
        "",
        "### 2. Failles 3D Ciblées par l'Algorithme d'Entraînement Nocturne (objectifs ; l'effet réel se lit dans les écarts mesurés ci-dessus)",
        "1. **Effondrement Face Arrière / Effet Panneau Plat (`clip_worst_view`)** : ciblé par sélection de dominance de Pareto stricte (`auto_rl/dominance.py`) qui interdit tout gain de score moyen payé par une baisse de la pire vue 360°.",
        "2. **Auto-Intersections & Topologie Non-Manifold (`self_intersections_exactes`, `nonmanifold_edge_fraction`)** : ciblé par test exact triangle-triangle de Möller (`auto_rl/mesh_metrics.py`) + régularisation spatiale 3D de continuité de vélocité dans `SparseStructureFlowModel`.",
        "3. **Fragmentation d'Îlots UV & Coutures (`fragment_area_fraction`)** : ciblé par soudure non-destructive préservant les UV (`auto_rl/weld_fragmented_mesh.py`).",
        "4. **Parois Fines, Rayons, Câbles & Assemblages Articulés** : ciblé par échantillonnage stratifié multi-pas de temps ($t_1 \\in [0.15, 0.50]$ pour les détails fins + $t_2 = 1 - t_1 \\in [0.50, 0.85]$ pour la structure globale) et par le pack **TRELLIS-500K**.",
        "",
        f"### 3. Pack de Données 500K+ Intégré (`{trellis_pack['dataset_repo']}` — `{trellis_pack['total_objects']:,}` objets 3D)",
        f"- Emplacement : `modele/renforce/3d/datasets/TRELLIS-500K/`",
        "- Composition vérifiée :",
    ])
    for k, v in trellis_pack.get("subsets", {}).items():
        lines.append(f"  - **{k}** : `{v:,}` objets 3D qualifiés")
    lines.extend([
        "",
        "### 4. Comment Choisir entre Modèle de Base et Modèle Renforcé",
        "- **Depuis l'interface AuroraIA** : utilise le sélecteur **« 🛡️ Base Intouchable ↔ ⚡ Modèle Renforcé (+Gains) »** dans la barre supérieure de chaque module.",
        "- **Depuis l'API / CLI** : `POST /api/models/reinforced-select` avec `{\"module\": \"3d\", \"variant\": \"renforce\"}` (ou `\"base\"`). La variante `renforce` est refusée (HTTP 409, message d'erreur en français) tant qu'aucun adaptateur n'est promu pour le module.",
        "- **Arrêter l'entraînement nocturne à tout moment** :",
        "  - Finir proprement le cycle en cours puis s'arrêter : `/home/juan/AuroraIA/application/.venv/bin/python -m auto_rl.control stop_after_cycle`",
        "  - Arrêt coopératif immédiat : `/home/juan/AuroraIA/application/.venv/bin/python -m auto_rl.control stop`",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def get_reinforced_overview(state: Path = STATE) -> dict[str, Any]:
    """Retourne instantanément l'état Base vs Modèle Renforcé et les fiches `.md` pour tous les modules."""
    from .runtime import ungated_reinforced_allowed
    from .versions import selected_version

    state = Path(state).resolve()
    master_md_path = RENFORCE_ROOT / "GAINS_MODELES_RENFORCES.md"
    if not master_md_path.is_file():
        sync_all_reinforced_models(state)

    modules_out: dict[str, dict[str, Any]] = {}
    outdated_sheets = False
    for mod, meta in ALL_UI_MODULES.items():
        mod_dir = RENFORCE_ROOT / mod
        manifest = read_json(mod_dir / "manifest.json", {})
        gains_md_path = mod_dir / "GAINS.md"
        sel = selected_version(mod, state)
        # Checked against the official registry on every read, so a manifest written
        # before this rule (or by another tool) cannot present itself as available.
        status = honest_status(manifest, state, mod)
        has_reinforced = bool(
            status == PROMOTED_STATUS
            and manifest.get("adapter")
            and Path(manifest["adapter"]).is_file()
        )
        selected_variant = "renforce" if sel in {"validated", "renforce"} else "base"
        is_reinforced_effective = has_reinforced and selected_variant == "renforce"
        gains_markdown = gains_md_path.read_text(encoding="utf-8") if gains_md_path.is_file() else ""
        # The sheets on disk were rendered from the stored status. When that status no
        # longer holds, say so instead of showing "vérifié" until the next sync rewrites them.
        if manifest.get("status") != status:
            outdated_sheets = True
            if gains_markdown:
                gains_markdown = STALE_SHEET_NOTICE + gains_markdown
        modules_out[mod] = {
            **meta,
            **manifest,
            "status": status,
            "promoted_officially": status == PROMOTED_STATUS,
            "selected_version": sel,
            "selected_variant": selected_variant,
            "active_variant": selected_variant,
            "effective_variant": "renforce" if is_reinforced_effective else "base",
            "reinforced_available": has_reinforced,
            "gains_markdown": gains_markdown,
            "gains_md_path": f"modele/renforce/{mod}/GAINS.md",
        }

    master_markdown = master_md_path.read_text(encoding="utf-8") if master_md_path.is_file() else ""
    if outdated_sheets and master_markdown:
        master_markdown = STALE_SHEET_NOTICE + master_markdown
    return {
        "renforce_root": str(RENFORCE_ROOT),
        "master_markdown_path": "modele/renforce/GAINS_MODELES_RENFORCES.md",
        "master_markdown": master_markdown,
        # True when this process was started with the explicit opt-in that lets the runtime
        # attach an unpromoted adapter; `effective_variant` above never counts that bypass.
        "ungated_opt_in": ungated_reinforced_allowed(),
        "modules": modules_out,
    }

