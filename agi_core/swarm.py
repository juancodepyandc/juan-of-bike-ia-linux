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
                          memory_module=None, history=None, store=None, lease_owner=None):
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
        agent = AutonomousMissionAgent(
            mission_id, request_text, workspace, selected, permissions,
            store=store, lease_owner=lease_owner, additional_context="\n\n".join(context))
        result = await agent.run()
        if memory_module and result and agent.state['status'] == 'completed':
            await memory_module.embed_experience(
                context="Mission: " + request_text, outcome=result,
                metadata={"mission_id":mission_id,"workspace":workspace,
                          "verification":"explicit_checks_only",
                          "evidence_count":len(agent.state['evidence'])})
        return result

    async def delegate(self, task: str) -> str:
        # Utilisé pour les tâches internes (comme l'auto-guérison) sans UI distante
        logger.info(f"[SUPERVISOR] Délégation interne (non-mission) : {task}")
        
        oracle_sys = "Tu es l'Orchestrateur Interne. On te soumet une tâche de fond (souvent une analyse de log ou d'erreur système). Produis une réponse concise avec ton analyse et tes recommandations d'architecture."
        
        output = ""
        def on_token(t):
            nonlocal output
            output += t
            
        await llm.generate_stream(oracle_sys, task, on_token, llm.default_model) # Modèle par défaut pour l'interne
        logger.info(f"[SUPERVISOR] Résultat de l'introspection : {output[:200]}...")
        return output
