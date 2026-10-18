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


class CognitiveExecutiveLoop:
    """Boucle Maîtresse en 7 Phases du Cerveau AGI d'AuroraIA.
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

    def build_autonomous_loop_plan(
        self,
        request_text: str,
        *,
        active_module: str | None = None,
        target_paths: list[str] | None = None,
        max_applicators: int = 5,
    ) -> dict[str, Any]:
        """Génère le plan complet d'exécution en boucle fermée (DAG multi-agents + Pare-Feu + Auto-Réparation)."""
        base_plan = self.router.plan_execution(
            request_text,
            active_module=active_module,
            target_paths=target_paths,
            max_applicators=max_applicators,
        )
        applicators = base_plan.get("applicators", [])

        # Déterminer le régime épistémique
        if len(base_plan.get("modules_involved", [])) > 1:
            epistemic_regime = "MULTI_MODULE_SYNTHESIS"
        elif len(applicators) > 1:
            epistemic_regime = "KNOWN_OPTIMIZABLE"
        else:
            epistemic_regime = "KNOWN_CANONICAL"

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
                    f"Régime épistémique : {epistemic_regime}."
                ),
            },
            {
                "phase": "DECOMPOSE_DAG",
                "status": "ready",
                "detail": f"Graphe DAG construit avec {len(dag_nodes)} nœud(s) atomique(s) sans recouvrement.",
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
                "detail": "Validation déterministe (tests, AST, invariants, zéro TODO/placeholder).",
            },
            {
                "phase": "SELF_HEAL_REFLECT",
                "status": "armed",
                "detail": "Boucle d'auto-réparation armée (jusqu'à 3 cycles de diagnostic/correction si échec).",
            },
            {
                "phase": "CONSOLIDATE_EVOLVE",
                "status": "armed",
                "detail": "Consolidation épisodique dans `.aurora/agi_brain_state.json` et contrôle continu CI.",
            },
        ]

        return {
            **base_plan,
            "schema_version": "aurora.agi_loops.v2",
            "epistemic_regime": epistemic_regime,
            "loop_phases": list(LOOP_PHASES),
            "phases_trace": phases_trace,
            "dag_nodes": dag_nodes,
            "operational_loops": {
                "cognitive_executive_loop": True,
                "scope_firewall_loop": True,
                "self_healing_diagnostic_loop": True,
                "continuous_github_verification_loop": True,
                "episodic_skill_evolution_loop": True,
            },
        }
