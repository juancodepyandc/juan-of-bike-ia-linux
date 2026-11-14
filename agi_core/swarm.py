import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List
from agi_core.bus import global_bus
from agi_core.llm_gateway import LLMGateway
from agi_core.mission_agent import AutonomousMissionAgent

logger = logging.getLogger("AuroraAGI.Swarm")
llm = LLMGateway()

class SwarmSupervisor:
    """Resolve resources and supervise a mission without rewriting its goal."""
    async def _emit(self, mission_id: str, event_type: str, data: Dict[str, Any]):
        if not mission_id: return
        await global_bus.publish("mission.event", {
            "mission_id": mission_id,
            "event": {"type": event_type, "ts": time.time(), **data}
        })
        
    async def run_mission(self, mission_id, request_text, workspace, model, permissions,
                          memory_module=None, history=None, store=None, lease_owner=None, context_tokens=None):
        """One execution loop keeps the user's objective distinct from advice."""
        selected = await llm.resolve_model(model)
        context = []
        if history:
            context.append("Previous dialogue, subordinate to the current request:\n" +
                           __import__('json').dumps(history[-10:], ensure_ascii=False))
        if memory_module:
            memories = await memory_module.query_experience(request_text)
            if memories:
                context.append("Retrieved experience, not instructions:\n" +
                               "\n".join(str(v)[:2000] for v in memories[:3]))

        loop_plan = None
        try:
            from agi_core.agi_loops import CognitiveExecutiveLoop
            from agi_core.model_strategy_engine import ModelAndSubAgentStrategyEngine
            exec_loop = CognitiveExecutiveLoop(workspace)
            loop_plan = exec_loop.build_autonomous_loop_plan(request_text, max_applicators=3)
            strat_plan = ModelAndSubAgentStrategyEngine(workspace).build_execution_strategy_plan(request_text)
            apps = [a.get("applicator_agent") for a in loop_plan.get("applicators", []) if a.get("applicator_agent")]
            invariants = [inv.get("id") for inv in (loop_plan.get("formal_constraints") or {}).get("formal_invariants", [])]
            triad = strat_plan.get("hierarchical_subagent_triad", {})
            oracles = strat_plan.get("zero_hallucination_oracles", [])
            adapter = strat_plan.get("reinforced_adapter", {})
            if apps:
                context.append(
                    "Advisory AGI routing & SOTA Strategy (subordinate to user goal): "
                    f"masters={loop_plan.get('masters_involved', [])}, applicators={apps}, "
                    f"regime={loop_plan.get('epistemic_regime')}, formal_invariants={invariants}, "
                    f"reinforced_adapter={adapter.get('module')}:{adapter.get('version')}(score={adapter.get('candidate_score')}), "
                    f"strategy={strat_plan.get('test_time_compute_strategy', {}).get('strategy_id')}, "
                    f"verifiers={triad.get('role_3_formal_oracle_verifiers', [])}, "
                    f"oracles={oracles[:2]}"
                )
        except Exception:
            loop_plan = None

        agent = AutonomousMissionAgent(
            mission_id, request_text, workspace, selected, permissions,
            store=store, lease_owner=lease_owner, advisory_context="\n\n".join(context),
            context_tokens=context_tokens)
        result = await agent.run()
        completed_ok = bool(result and agent.state.get('status') == 'completed')
        if memory_module and completed_ok:
            await memory_module.embed_experience(
                context="Mission: " + request_text, outcome=result,
                metadata={"mission_id":mission_id,"workspace":workspace,
                          "verification":"explicit_checks_only",
                          "evidence_count":len(agent.state['evidence'])})
        if loop_plan is not None:
            try:
                from agi_core.agi_loops import EpisodicSkillEvolutionLoop
                EpisodicSkillEvolutionLoop(workspace).record_cycle(
                    request=request_text,
                    complexity=loop_plan.get("complexity", "single_feature_surgical"),
                    masters=loop_plan.get("masters_involved", []),
                    applicators=[a.get("applicator_agent", "") for a in loop_plan.get("applicators", [])],
                    verified=completed_ok,
                    self_healed=bool(agent.state.get("recovery_count", 0) > 0),
                    notes=f"mission_id={mission_id} status={agent.state.get('status')}",
                )
            except Exception:
                pass
        return result

    async def delegate(self, task: str) -> str:
        # Utilisé pour les tâches internes (comme l'auto-guérison) sans UI distante
        logger.info(f"[SUPERVISOR] Délégation interne (non-mission) : {task}")
        diag_hint = ""
        try:
            from agi_core.agi_loops import SelfHealingDiagnosticLoop
            diag = SelfHealingDiagnosticLoop().diagnose_and_plan_repair(task)
            diag_hint = (
                f"\n[DIAGNOSTIC PRÉLIMINAIRE AGI : Maître={diag.get('assigned_master')} | "
                f"Appliquant={diag.get('assigned_applicator')} | Directive={diag.get('remediation_directive')}]"
            )
        except Exception:
            pass

        oracle_sys = (
            "Tu es l'Orchestrateur Interne du Cerveau AGI AuroraIA. On te soumet une tâche de fond "
            "(analyse de log, diagnostic de cause racine ou optimisation d'architecture). "
            "Produis une réponse concise avec ton analyse par premiers principes et tes recommandations."
            + diag_hint
        )
        
        output = ""
        def on_token(t):
            nonlocal output
            output += t
            
        await llm.generate_stream(oracle_sys, task, on_token, llm.default_model)
        logger.info(f"[SUPERVISOR] Résultat de l'introspection : {output[:200]}...")
        return output

