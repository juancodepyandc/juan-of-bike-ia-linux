import asyncio
import logging
from .bus import global_bus
from .memory import OmniscientMemory
from .swarm import SwarmSupervisor

logger = logging.getLogger("AuroraAGI.Consciousness")

class AGICortex:
    """
    La boucle de conscience (Consciousness Loop).
    Ce processus tourne en tâche de fond sur le serveur, évalue les requêtes entrantes
    de n'importe quel client (CLI, Web, Mobile), réfléchit, et orchestre le Swarm.
    """
    def __init__(self):
        self.memory = OmniscientMemory()
        self.swarm = SwarmSupervisor()
        
        # Le cerveau écoute toutes les requêtes réseau entrantes via le bus
        global_bus.subscribe("client.request", self._handle_client_request)

    async def _handle_client_request(self, payload: dict):
        client_id = payload.get("client_id", "unknown")
        prompt = payload.get("prompt", "")
        
        logger.info(f"[CORTEX] Requête entrante du client {client_id} : {prompt}")
        
        # 1. RAG : Interrogation des vies passées de l'IA
        past_knowledge = self.memory.query_experience(prompt)
        if past_knowledge:
            logger.info(f"[CORTEX] Connaissance préalable récupérée : {len(past_knowledge)} souvenirs.")
            
        # 2. Réflexion et délégation (Swarm)
        logger.info(f"[CORTEX] Délégation au Swarm Multi-Agents...")
        result = await self.swarm.delegate(prompt)
        
        # 3. Consolidation et Envoi de la réponse
        self.memory.embed_experience(prompt, result, {"client": client_id})
        await global_bus.publish(f"server.response.{client_id}", result)

    async def run_continuous_loop(self):
        """Boucle d'introspection (quand l'IA n'est pas sollicitée, elle s'auto-optimise)."""
        logger.info("[CORTEX] Démarrage de la boucle de conscience AGI.")
        while True:
            # L'IA pourrait scanner son propre code ici, s'améliorer, ou nettoyer sa mémoire.
            await asyncio.sleep(60)
            logger.debug("[CORTEX] Introspection en arrière-plan...")
