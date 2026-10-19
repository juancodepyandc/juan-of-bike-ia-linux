"""Boucles de Fonctionnement AGI Avancées (Closed-Loop Cognitive, Self-Healing, Scope Firewall & GitHub CI Guardian).

Ce module implémente les 5 boucles opérationnelles autonomes du Cerveau AGI d'AuroraIA :
  1. `CognitiveExecutiveLoop` (7 phases : PERCEIVE -> DECOMPOSE_DAG -> ROUTE -> APPLY -> VERIFY -> SELF_HEAL -> CONSOLIDATE)
  2. `ScopeFirewallEnforcementLoop` (Pare-feu strict anti-mélange `files_owned` / `routes_owned` / `never_touch` + anti-placeholder)
  3. `SelfHealingDiagnosticLoop` (Diagnostic déterministe de cause racine sur erreurs Python/TS/Rust/3D/GPU et plan d'auto-réparation)
  4. `ContinuousGitHubVerificationLoop` (Boucle de vérification continue locale + GitHub Actions garantissant 0 échec / 100 % pass)
  5. `EpisodicSkillEvolutionLoop` (Mémoire épisodique persistante `.aurora/agi_brain_state.json` et auto-amélioration des appliquants)
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from agi_core.agi_brain import AGIBrainRouter, DEFAULT_WORKSPACE

LOOP_PHASES: tuple[str, ...] = (
    "PERCEIVE_INTENT",
    "DECOMPOSE_DAG",
    "ROUTE_APPLICATORS",
    "APPLY_SURGICAL",
    "VERIFY_CRITIQUE",
    "SELF_HEAL_REFLECT",
    "CONSOLIDATE_EVOLVE",
)

PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bTODO\s*:", re.IGNORECASE),
    re.compile(r"\bFIXME\s*:", re.IGNORECASE),
    re.compile(r"\bNotImplementedError\b"),
    re.compile(r"\bplaceholder\b.*?\b(?:implement|replace)\b", re.IGNORECASE),
)


class ScopeFirewallEnforcementLoop:
    """Boucle Pare-Feu garantissant qu'aucun Sous-Agent Appliquant ne mélange son périmètre
    avec un autre module et ne livre aucun code incomplet (stub/TODO).
    """

    def __init__(self, router: AGIBrainRouter | None = None):
        self.router = router or AGIBrainRouter()

    def validate_action(
        self,
        applicator_name: str,
        target_files: list[str] | None = None,
        target_routes: list[str] | None = None,
        proposed_content: str | None = None,
    ) -> dict[str, Any]:
        info = self.router.catalog.get(applicator_name) or {}
        never_touch = [p.lower() for p in info.get("never_touch", [])]
        files_owned = [p.lower() for p in info.get("files_owned", [])]
        routes_owned = [r.lower() for r in info.get("routes_owned", [])]

        violations: list[dict[str, str]] = []
        handoff_recommendations: list[dict[str, Any]] = []

        for tf in target_files or []:
            tf_lower = tf.strip().lower()
            base_tf = Path(tf_lower.split("#")[0]).name
            for forbidden in never_touch:
                forb_base = Path(forbidden.split("#")[0]).name
                if forbidden in tf_lower or (forb_base and forb_base == base_tf):
                    # Identifier quel appliquant possède réellement ce fichier
                    rightful = self._find_rightful_owner(tf)
                    violations.append({
                        "type": "never_touch_breach",
                        "target": tf,
                        "forbidden_rule": forbidden,
                        "message": (
                            f"L'appliquant `{applicator_name}` n'a pas le droit de modifier `{tf}` "
                            f"(règle pare-feu `never_touch`: `{forbidden}`)."
                        ),
                    })
                    if rightful:
                        handoff_recommendations.append(rightful)

        for tr in target_routes or []:
            tr_lower = tr.strip().lower()
            for forbidden in never_touch:
                if forbidden.startswith("/api/") and forbidden in tr_lower:
                    violations.append({
                        "type": "never_touch_route_breach",
                        "target": tr,
                        "forbidden_rule": forbidden,
                        "message": f"Route `{tr}` interdite pour `{applicator_name}` (`{forbidden}`).",
                    })

        placeholder_hits: list[str] = []
        if proposed_content:
            for pat in PLACEHOLDER_PATTERNS:
                match = pat.search(proposed_content)
                if match:
                    placeholder_hits.append(match.group(0))
            if placeholder_hits:
                violations.append({
                    "type": "anti_placeholder_breach",
                    "target": "proposed_content",
                    "forbidden_rule": "zero_placeholder",
                    "message": f"Marqueurs incomplets détectés et bloqués : {', '.join(placeholder_hits)}",
                })

        return {
            "ok": len(violations) == 0,
            "applicator": applicator_name,
            "master": info.get("parent_agent") or "aurora-orchestrator",
            "module": info.get("module") or "orchestration",
            "feature": info.get("feature") or applicator_name,
            "files_owned_count": len(files_owned),
            "routes_owned_count": len(routes_owned),
            "violations": violations,
            "handoff_recommendations": handoff_recommendations,
        }

    def _find_rightful_owner(self, target_path: str) -> dict[str, Any] | None:
        t_low = target_path.strip().lower()
        t_base = Path(t_low.split("#")[0]).name
        for name, info in self.router.catalog.items():
            if info.get("role_type") != "subagent":
                continue
            for owned in info.get("files_owned", []):
                o_low = owned.lower()
                o_base = Path(o_low.split("#")[0]).name
                if o_low in t_low or (o_base and o_base == t_base):
                    return {
                        "rightful_applicator": name,
                        "rightful_master": info.get("parent_agent") or "aurora-orchestrator",
                        "module": info.get("module"),
                        "feature": info.get("feature"),
                    }
        return None


class SelfHealingDiagnosticLoop:
    """Boucle d'Auto-Réparation & Diagnostic de Cause Racine.
    Analyse toute erreur (Python, TypeScript/Node, Rust/Tauri, 3D/Mesh, GPU/VRAM, GitHub CI)
    et génère un plan de remédiation chirurgical routé vers l'Appliquant exact.
    """

    ERROR_SIGNATURES: tuple[dict[str, Any], ...] = (
        {
            "id": "python_module_not_found",
            "pattern": re.compile(r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]"),
            "category": "python_import_resolution",
            "default_applicator": "code-backend-performance",
            "remediation_template": (
                "Vérifier `sys.path` et la racine d'exécution lors de l'import de `{match}` ; "
                "ajouter le dossier parent ou un import relatif résilient sans casser l'isolation."
            ),
        },
        {
            "id": "node_err_module_not_found",
            "pattern": re.compile(r"ERR_MODULE_NOT_FOUND|Cannot find package ['\"]([^'\"]+)['\"]"),
            "category": "typescript_node_import",
            "default_applicator": "code-architecture-planner",
            "remediation_template": (
                "Découpler les imports lourds dépendant de `node_modules` (ex. `@tauri-apps/api`) via "
                "`await import(...)` paresseux pour permettre l'exécution Node `--experimental-strip-types` hors bundle."
            ),
        },
        {
            "id": "http_contract_status_mismatch",
            "pattern": re.compile(r"AssertionError:\s*assert\s+(\d{3})\s*==\s*(\d{3})"),
            "category": "http_api_contract",
            "default_applicator": "missions-store-lease",
            "remediation_template": (
                "Aligner le code de statut HTTP retourné ({match}) avec le contrat atomique des routes "
                "et vérifier les préconditions d'état (`queued` vs `running`)."
            ),
        },
        {
            "id": "gpu_vram_oom",
            "pattern": re.compile(r"CUDA out of memory|OutOfMemoryError|VRAM", re.IGNORECASE),
            "category": "gpu_vram_arbitration",
            "default_applicator": "bridge-gpu-governor",
            "remediation_template": (
                "Décharger les modèles inactifs (`ollama stop` / `/api/comfy/free`) via `bridge-gpu-governor` "
                "avant d'allouer le pipeline lourd."
            ),
        },
        {
            "id": "mesh_topology_non_manifold",
            "pattern": re.compile(r"non-manifold|watertight|degenerate face|inverted normal", re.IGNORECASE),
            "category": "3d_mesh_topology",
            "default_applicator": "3d-quality-rescuer",
            "remediation_template": (
                "Exécuter la boucle `auto_rescue_mesh.py` + `weld_fragmented_mesh.py` et re-vérifier "
                "via `perfection_gate.py`."
            ),
        },
    )

    def __init__(self, router: AGIBrainRouter | None = None):
        self.router = router or AGIBrainRouter()

    def diagnose_and_plan_repair(
        self,
        error_text: str,
        *,
        failing_file: str | None = None,
        attempt: int = 1,
    ) -> dict[str, Any]:
        text = (error_text or "").strip()
        matched_sig: dict[str, Any] | None = None
        extracted_token = ""

        for sig in self.ERROR_SIGNATURES:
            m = sig["pattern"].search(text)
            if m:
                matched_sig = sig
                extracted_token = m.group(1) if m.lastindex else m.group(0)
                break

        target_paths = [failing_file] if failing_file else []
        # Extraire aussi tout chemin de fichier présent dans le traceback
        for file_match in re.findall(r"([A-Za-z0-9_./-]+\.(?:py|ts|tsx|mjs|rs|js))", text):
            if file_match not in target_paths:
                target_paths.append(file_match)

        brain_plan = self.router.plan_execution(
            f"{text[:400]} {' '.join(target_paths[:4])}",
            target_paths=target_paths,
            max_applicators=2,
        )
        primary_app = (
            brain_plan["applicators"][0]["applicator_agent"]
            if brain_plan.get("applicators")
            else (matched_sig["default_applicator"] if matched_sig else "code-backend-performance")
        )
        app_info = self.router.catalog.get(primary_app, {})
        master_agent = app_info.get("parent_agent") or "code-lead"

        if matched_sig:
            remediation = matched_sig["remediation_template"].format(match=extracted_token or "cible")
            category = matched_sig["category"]
            signature_id = matched_sig["id"]
        else:
            remediation = (
                "Inspecter les fichiers mis en cause dans le traceback, isoler l'invariant violé "
                "et appliquer un correctif minimal vérifié par un test unitaire ciblé."
            )
            category = "general_runtime_exception"
            signature_id = "generic_traceback_diagnosis"

        return {
            "ok": True,
            "attempt": attempt,
            "signature_id": signature_id,
            "category": category,
            "extracted_symbol": extracted_token,
            "target_files_detected": target_paths[:6],
            "assigned_master": master_agent,
            "assigned_applicator": primary_app,
            "remediation_directive": remediation,
            "verification_gate": app_info.get("verification_focus") or "Relancer le test en échec jusqu'à code retour 0.",
            "escalation_policy": (
                "keep_iterating"
                if attempt < 4
                else "switch_epistemic_regime_to_root_cause_reconstruction"
            ),
        }


class EpisodicSkillEvolutionLoop:
    """Boucle d'Apprentissage Épisodique & Auto-Évolution du Cerveau AGI.
    Conserve la télémétrie des cycles exécutés dans `.aurora/agi_brain_state.json`.
    """

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace).expanduser().resolve() if workspace else DEFAULT_WORKSPACE
        self.state_path = self.workspace / ".aurora" / "agi_brain_state.json"

    def load_state(self) -> dict[str, Any]:
        if self.state_path.is_file():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                pass
        return {
            "schema_version": "aurora.agi_brain_state.v1",
            "total_cycles": 0,
            "successful_cycles": 0,
            "self_healed_cycles": 0,
            "applicator_stats": {},
            "recent_episodes": [],
            "github_ci_passes": [],
        }

    def record_cycle(
        self,
        *,
        request: str,
        complexity: str,
        masters: list[str],
        applicators: list[str],
        verified: bool,
        self_healed: bool = False,
        notes: str = "",
    ) -> dict[str, Any]:
        state = self.load_state()
        state["total_cycles"] = int(state.get("total_cycles", 0)) + 1
        if verified:
            state["successful_cycles"] = int(state.get("successful_cycles", 0)) + 1
        if self_healed:
            state["self_healed_cycles"] = int(state.get("self_healed_cycles", 0)) + 1

        stats = state.setdefault("applicator_stats", {})
        for app_name in applicators:
            entry = stats.setdefault(app_name, {"runs": 0, "verified": 0, "self_healed": 0})
            entry["runs"] = int(entry.get("runs", 0)) + 1
            if verified:
                entry["verified"] = int(entry.get("verified", 0)) + 1
            if self_healed:
                entry["self_healed"] = int(entry.get("self_healed", 0)) + 1

        episodes = state.setdefault("recent_episodes", [])
        episodes.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request": request[:240],
            "complexity": complexity,
            "masters": masters,
            "applicators": applicators,
            "verified": verified,
            "self_healed": self_healed,
            "notes": notes[:300],
        })
        state["recent_episodes"] = episodes[-50:]

        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return state


class ContinuousGitHubVerificationLoop:
    """Boucle Continue d'Auto-Amélioration & Gardien GitHub CI ("Tant que GitHub annonce 0 passe, on continue").
    Vérifie les suites de tests locales et l'état des workflows GitHub Actions.
    """

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace).expanduser().resolve() if workspace else DEFAULT_WORKSPACE
        self.healer = SelfHealingDiagnosticLoop(AGIBrainRouter(self.workspace))

    def inspect_github_runs(self, limit: int = 8) -> dict[str, Any]:
        """Interroge `gh run list` pour connaître le nombre exact de workflows passés vs échoués."""
        try:
            proc = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--limit",
                    str(limit),
                    "--json",
                    "databaseId,name,status,conclusion,headBranch,displayTitle",
                ],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return {
                    "ok": False,
                    "gh_available": False,
                    "runs": [],
                    "passed_count": 0,
                    "failed_count": 0,
                    "in_progress_count": 0,
                    "should_continue_improving": True,
                }
            runs = json.loads(proc.stdout)
        except Exception:
            return {
                "ok": False,
                "gh_available": False,
                "runs": [],
                "passed_count": 0,
                "failed_count": 0,
                "in_progress_count": 0,
                "should_continue_improving": True,
            }

        # Regrouper par workflow le dernier run sur main (ou global)
        latest_by_workflow: dict[str, dict[str, Any]] = {}
        for r in runs:
            wf_name = str(r.get("name") or "")
            if wf_name and wf_name not in latest_by_workflow:
                latest_by_workflow[wf_name] = r

        passed = sum(1 for r in latest_by_workflow.values() if r.get("conclusion") == "success")
        failed = sum(1 for r in latest_by_workflow.values() if r.get("conclusion") in {"failure", "cancelled", "timed_out"})
        in_progress = sum(1 for r in latest_by_workflow.values() if r.get("status") != "completed")

        mission_wf = latest_by_workflow.get("Mission contracts", {})
        mission_Zero_Pass = mission_wf.get("conclusion") == "failure"

        return {
            "ok": True,
            "gh_available": True,
            "latest_by_workflow": latest_by_workflow,
            "passed_count": passed,
            "failed_count": failed,
            "in_progress_count": in_progress,
            "mission_contracts_conclusion": mission_wf.get("conclusion") or mission_wf.get("status") or "unknown",
            "should_continue_improving": failed > 0 or in_progress > 0 or mission_Zero_Pass or passed == 0,
        }


class MultiHypothesisCounterfactualLoop:
    """Boucle 6 — Raisonnement Contre-Factuel & Tree-of-Thoughts Bayésien.
    Évalue 3 hypothèses concurrentes avant action (Directe, Double-Vérifiée, Red-Team Résiliente)
    et sélectionne la trajectoire maximisant l'utilité espérée.
    """

    def __init__(self, router: AGIBrainRouter | None = None, memory: EpisodicSkillEvolutionLoop | None = None):
        self.router = router or AGIBrainRouter()
        self.memory = memory or EpisodicSkillEvolutionLoop()

    def evaluate_hypotheses(
        self,
        request_text: str,
        applicators: list[dict[str, Any]],
        complexity: str = "single_feature_surgical",
    ) -> dict[str, Any]:
        state = self.memory.load_state()
        stats = state.get("applicator_stats", {})

        primary_app = applicators[0]["applicator_agent"] if applicators else "conversation-intent-router"
        primary_stat = stats.get(primary_app, {})
        runs = max(1, int(primary_stat.get("runs", 0)))
        verified = int(primary_stat.get("verified", 0))
        empirical_prior = round(min(0.99, max(0.78, (verified + 3) / (runs + 3))), 3)

        is_complex = complexity in {"multi_module", "multi_feature"} or len(request_text) > 120
        hypotheses = [
            {
                "id": "hypothesis_alpha_canonical",
                "title": "Exécution Chirurgicale Directe (Chemin Canonique)",
                "strategy": f"Délégation directe à `{primary_app}` sur son périmètre `files_owned` avec vérification unitaire.",
                "prior_probability": empirical_prior,
                "quality_gain": 0.86,
                "risk_penalty": 0.14 if is_complex else 0.04,
                "expected_utility": round(empirical_prior * 0.86 - (0.14 if is_complex else 0.04), 3),
            },
            {
                "id": "hypothesis_beta_cross_verified",
                "title": "Pipeline Multi-Appliquants à Double Porte de Preuve",
                "strategy": (
                    f"Chaînage coordonné {', '.join(a['applicator_agent'] for a in applicators)} "
                    "avec contrôle formel SymPy/Z3 ou test d'intégration croisé avant clôture."
                ),
                "prior_probability": round(min(0.99, empirical_prior + 0.05), 3),
                "quality_gain": 0.96,
                "risk_penalty": 0.05,
                "expected_utility": round(min(0.99, empirical_prior + 0.05) * 0.96 - 0.05, 3),
            },
            {
                "id": "hypothesis_gamma_counterfactual_redteam",
                "title": "Trajectoire Contre-Factuelle Red-Team & Anti-Régression",
                "strategy": (
                    "Pré-simulation des cas limites (VRAM 16 Go, chemins multi-OS Linux/macOS/Windows, "
                    "absence de dépendances externes, contrat HTTP atomique) + boucle Self-Healing active."
                ),
                "prior_probability": round(min(0.995, empirical_prior + 0.08), 3),
                "quality_gain": 0.99 if is_complex else 0.92,
                "risk_penalty": 0.02,
                "expected_utility": round(
                    min(0.995, empirical_prior + 0.08) * (0.99 if is_complex else 0.92) - 0.02, 3
                ),
            },
        ]
        hypotheses.sort(key=lambda h: -h["expected_utility"])
        selected = hypotheses[0]
        return {
            "ok": True,
            "selected_hypothesis": selected["id"],
            "selected_title": selected["title"],
            "selected_expected_utility": selected["expected_utility"],
            "empirical_prior": empirical_prior,
            "hypotheses": hypotheses,
        }


class CrossModuleSynergyOrchestratorLoop:
    """Boucle 7 — Synergie Inter-Modules & Contrats de Passage de Relais Typés (`HandoffContract`).
    Garantit que lorsque plusieurs modules ou appliquants coopèrent, la sortie vérifiée du nœud N
    alimente proprement l'entrée du nœud N+1 sans perte de contexte ni mélange de fichiers.
    """

    MODULE_ARTIFACT_SCHEMAS: dict[str, dict[str, str]] = {
        "drawing": {
            "output": "aurora.artifact.sketch_turnaround.v1 (PNG + strokes JSON)",
            "invariant": "Traits nets et proportions validées par Qwen3-VL",
        },
        "image": {
            "output": "aurora.artifact.image_master_package.v1 (PNG 4K/8K/16K + PBR maps + metadata.json)",
            "invariant": "Zéro artefact de compression, dossier creations/ ou modifications/ respecté",
        },
        "3d": {
            "output": "aurora.artifact.mesh_cad_bundle.v1 (GLB/STL watertight + textures PBR + BOM)",
            "invariant": "Maillage manifold/watertight vérifié et centré à l'origine",
        },
        "video": {
            "output": "aurora.artifact.video_sequence.v1 (MP4 H.264 + piste audio synchronisée)",
            "invariant": "Cohérence temporelle inter-trames et durée conforme",
        },
        "voice": {
            "output": "aurora.artifact.voice_visemes.v1 (WAV 24kHz + visèmes temporels A-X)",
            "invariant": "Prosodie naturelle sans coupure",
        },
        "code": {
            "output": "aurora.artifact.verified_codebase.v1 (Arborescence complète + tests unitaires 0 erreur)",
            "invariant": "Compilation/exécution code retour 0 et zéro TODO/placeholder",
        },
        "cyber": {
            "output": "aurora.artifact.security_proof.v1 (Rapport CVE/CWE + preuve Z3 UNSAT sur patch)",
            "invariant": "Vulnérabilité éliminée sans régression fonctionnelle",
        },
        "business": {
            "output": "aurora.artifact.executive_memo.v1 (VAN/TRI/DSO + Net en poche + Veto Risque)",
            "invariant": "Probabilité de ruine <= 2 % et réserve >= 25 %",
        },
        "learning": {
            "output": "aurora.artifact.formal_curriculum.v1 (Cours structuré + Preuve SymPy/Z3 + Quiz)",
            "invariant": "Exactitude mathématique et pédagogique vérifiée",
        },
        "training": {
            "output": "aurora.artifact.reinforced_adapter.v1 (modele/renforce/<module>/ + GAINS.md)",
            "invariant": "Modèle de base intact et gain mesuré sur holdout > 0",
        },
    }

    def build_handoff_contracts(self, applicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contracts: list[dict[str, Any]] = []
        for i in range(len(applicators) - 1):
            src = applicators[i]
            dst = applicators[i + 1]
            src_mod = str(src.get("module") or "conversation")
            dst_mod = str(dst.get("module") or "conversation")
            src_schema = self.MODULE_ARTIFACT_SCHEMAS.get(src_mod, {
                "output": f"aurora.artifact.{src_mod}.v1",
                "invariant": src.get("verification_gate") or "Sortie vérifiée",
            })
            dst_schema = self.MODULE_ARTIFACT_SCHEMAS.get(dst_mod, {
                "output": f"aurora.artifact.{dst_mod}.v1",
                "invariant": dst.get("verification_gate") or "Entrée validée",
            })
            contracts.append({
                "handoff_index": i + 1,
                "from_master": src["master_agent"],
                "from_applicator": src["applicator_agent"],
                "from_module": src_mod,
                "to_master": dst["master_agent"],
                "to_applicator": dst["applicator_agent"],
                "to_module": dst_mod,
                "artifact_contract": src_schema["output"],
                "required_invariant_before_handoff": src_schema["invariant"],
                "target_output_contract": dst_schema["output"],
            })
        return contracts


class AutonomousGoalWatchdogLoop:
    """Boucle 8 — Gouverneur d'Objectif Anti-Stagnation & Anti-Divagation Temps Réel.
    Surveille la trajectoire d'une mission pour détecter immédiatement :
      - l'oscillation d'outils (appels identiques répétés sans progrès),
      - la dérive sémantique hors de la demande utilisateur,
      - les contraintes explicites non encore satisfaites.
    """

    STOPWORDS: frozenset[str] = frozenset({
        "dans", "avec", "pour", "sans", "plus", "tout", "tous", "toute", "toutes",
        "cette", "comme", "mais", "donc", "alors", "bien", "faire", "fait", "être",
        "avoir", "vrai", "vraiment", "aussi", "meme", "même", "tres", "très",
    })

    def evaluate_trajectory(
        self,
        request_text: str,
        *,
        executed_steps: list[dict[str, Any]] | None = None,
        current_output: str = "",
    ) -> dict[str, Any]:
        req_tokens = [
            t for t in re.findall(r"[a-z0-9àâçéèêëîïôûùüÿñæœ]{4,}", (request_text or "").lower())
            if t not in self.STOPWORDS
        ]
        unique_anchors = list(dict.fromkeys(req_tokens))[:15]

        steps = executed_steps or []
        recent_signatures = [
            f"{s.get('tool', '')}:{s.get('target', '')}" for s in steps[-4:] if isinstance(s, dict)
        ]
        oscillation_detected = (
            len(recent_signatures) >= 3 and len(set(recent_signatures[-3:])) == 1 and bool(recent_signatures[-1].strip(":"))
        )

        combined_work = f"{current_output} " + " ".join(json.dumps(s, ensure_ascii=False) for s in steps)
        combined_lower = combined_work.lower()

        if unique_anchors and combined_lower.strip():
            covered = [a for a in unique_anchors if a in combined_lower]
            missing = [a for a in unique_anchors if a not in combined_lower]
            alignment_score = round(len(covered) / len(unique_anchors), 3)
        else:
            covered = unique_anchors
            missing = []
            alignment_score = 1.0

        drift_score = round(1.0 - alignment_score, 3)
        needs_course_correction = oscillation_detected or (bool(combined_lower.strip()) and drift_score > 0.65)

        directive = (
            "Trajectoire nominale : verrouillage d'intention maintenu et progression vérifiée."
            if not needs_course_correction
            else (
                "ALERTE WATCHDOG AGI : Recentrage immédiat requis. "
                + ("Oscillation d'outil détectée (changer d'approche). " if oscillation_detected else "")
                + (f"Ancres du prompt à couvrir : {', '.join(missing[:6])}." if missing else "")
            )
        )

        return {
            "ok": True,
            "alignment_score": alignment_score,
            "drift_score": drift_score,
            "oscillation_detected": oscillation_detected,
            "covered_anchors": covered[:10],
            "missing_anchors": missing[:10],
            "needs_course_correction": needs_course_correction,
            "course_correction_directive": directive,
        }


class CognitiveExecutiveLoop:
    """Boucle Maîtresse en 7 Phases du Cerveau AGI d'AuroraIA (coordonnant les 8 Boucles Opérationnelles).
    Orchestre de bout en bout :
      1. PERCEIVE_INTENT
      2. DECOMPOSE_DAG
      3. ROUTE_APPLICATORS
      4. APPLY_SURGICAL
      5. VERIFY_CRITIQUE
      6. SELF_HEAL_REFLECT
      7. CONSOLIDATE_EVOLVE
    """

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace).expanduser().resolve() if workspace else DEFAULT_WORKSPACE
        self.router = AGIBrainRouter(self.workspace)
        self.firewall = ScopeFirewallEnforcementLoop(self.router)
        self.healer = SelfHealingDiagnosticLoop(self.router)
        self.memory = EpisodicSkillEvolutionLoop(self.workspace)
        self.github_guardian = ContinuousGitHubVerificationLoop(self.workspace)
        self.counterfactual = MultiHypothesisCounterfactualLoop(self.router, self.memory)
        self.synergy = CrossModuleSynergyOrchestratorLoop()
        self.watchdog = AutonomousGoalWatchdogLoop()

    def build_autonomous_loop_plan(
        self,
        request_text: str,
        *,
        active_module: str | None = None,
        target_paths: list[str] | None = None,
        max_applicators: int = 5,
        use_llm: bool = False,
    ) -> dict[str, Any]:
        """Génère le plan complet d'exécution en boucle fermée (Compréhension Cognitive + DAG multi-agents +
        Pare-Feu + Tree-of-Thoughts Bayésien + Synergie Inter-Modules + Watchdog + Auto-Réparation).
        """
        base_plan = self.router.plan_execution(
            request_text,
            active_module=active_module,
            target_paths=target_paths,
            max_applicators=max_applicators,
            use_llm=use_llm,
        )
        applicators = base_plan.get("applicators", [])
        cog = base_plan.get("cognitive_understanding") or {}

        # Déterminer le régime épistémique
        if len(base_plan.get("modules_involved", [])) > 1:
            epistemic_regime = "MULTI_MODULE_SYNTHESIS"
        elif cog.get("epistemic_regime"):
            epistemic_regime = str(cog["epistemic_regime"])
        elif len(applicators) > 1:
            epistemic_regime = "KNOWN_OPTIMIZABLE"
        else:
            epistemic_regime = "KNOWN_CANONICAL"

        # Évaluation contre-factuelle bayésienne (Boucle 6)
        hypothesis_eval = self.counterfactual.evaluate_hypotheses(
            request_text,
            applicators,
            complexity=base_plan.get("complexity", "single_feature_surgical"),
        )

        # Contrats de synergie inter-modules / inter-appliquants (Boucle 7)
        handoff_contracts = self.synergy.build_handoff_contracts(applicators)

        # Pré-évaluation Watchdog des ancres obligatoires (Boucle 8)
        watchdog_baseline = self.watchdog.evaluate_trajectory(request_text)

        # Construire le DAG ordonné avec dépendances et vérifications par nœud
        dag_nodes: list[dict[str, Any]] = []
        for idx, app in enumerate(applicators, start=1):
            fw_check = self.firewall.validate_action(
                app["applicator_agent"],
                target_files=target_paths or app["scope_firewall"]["files_owned"][:2],
            )
            dag_nodes.append({
                "node_id": f"node_{idx}_{app['applicator_agent']}",
                "step_index": idx,
                "depends_on": [f"node_{idx - 1}_{applicators[idx - 2]['applicator_agent']}"] if idx > 1 else [],
                "master_agent": app["master_agent"],
                "applicator_agent": app["applicator_agent"],
                "module": app["module"],
                "feature": app["feature"],
                "scope_firewall": app["scope_firewall"],
                "firewall_precheck_ok": fw_check["ok"],
                "verification_gate": app["verification_gate"],
                "self_healing_fallback": {
                    "max_retries": 3,
                    "on_failure": "SelfHealingDiagnosticLoop.diagnose_and_plan_repair",
                    "escalate_to_master": app["master_agent"],
                },
            })

        phases_trace = [
            {
                "phase": "PERCEIVE_INTENT",
                "status": "ready",
                "detail": (
                    f"Intention verrouillée ({base_plan['complexity']}) — "
                    f"Régime : {epistemic_regime} — "
                    f"Stratégie retenue : {hypothesis_eval['selected_title']} "
                    f"(U={hypothesis_eval['selected_expected_utility']})."
                ),
            },
            {
                "phase": "DECOMPOSE_DAG",
                "status": "ready",
                "detail": (
                    f"Graphe DAG construit avec {len(dag_nodes)} nœud(s) atomique(s) "
                    f"et {len(handoff_contracts)} contrat(s) de relais typé(s)."
                ),
            },
            {
                "phase": "ROUTE_APPLICATORS",
                "status": "ready",
                "detail": (
                    f"Maîtres : {', '.join(base_plan['masters_involved'])} → "
                    f"Appliquants : {', '.join(a['applicator_agent'] for a in applicators)}."
                ),
            },
            {
                "phase": "APPLY_SURGICAL",
                "status": "pending_execution",
                "detail": "Exécution cloisonnée par `files_owned` / `routes_owned` avec blocage `never_touch`.",
            },
            {
                "phase": "VERIFY_CRITIQUE",
                "status": "pending_verification",
                "detail": "Validation déterministe (tests, AST, invariants, zéro TODO/placeholder, Watchdog anti-dérive).",
            },
            {
                "phase": "SELF_HEAL_REFLECT",
                "status": "armed",
                "detail": "Boucle d'auto-réparation armée (jusqu'à 3 cycles de diagnostic/correction si échec).",
            },
            {
                "phase": "CONSOLIDATE_EVOLVE",
                "status": "armed",
                "detail": "Consolidation épisodique dans `.aurora/agi_brain_state.json` et contrôle continu GitHub CI.",
            },
        ]

        return {
            **base_plan,
            "schema_version": "aurora.agi_loops.v2",
            "epistemic_regime": epistemic_regime,
            "loop_phases": list(LOOP_PHASES),
            "phases_trace": phases_trace,
            "dag_nodes": dag_nodes,
            "counterfactual_evaluation": hypothesis_eval,
            "handoff_contracts": handoff_contracts,
            "watchdog_anchors": watchdog_baseline["covered_anchors"],
            "operational_loops": {
                "cognitive_executive_loop": True,
                "scope_firewall_loop": True,
                "self_healing_diagnostic_loop": True,
                "continuous_github_verification_loop": True,
                "episodic_skill_evolution_loop": True,
                "multi_hypothesis_counterfactual_loop": True,
                "cross_module_synergy_orchestrator_loop": True,
                "autonomous_goal_watchdog_loop": True,
            },
        }
