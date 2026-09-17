#!/usr/bin/env python3
"""
Point d'entrée du Démon AGI Aurora (Le vrai cerveau backend).
Doit tourner en permanence avec bridge_server.py.
"""
import asyncio
import logging
import os
import traceback
from agi_core.consciousness import AGICortex
from agi_core.bus import global_bus

def check_for_previous_crashes(brain):
    log_file = os.path.expandvars("${TMPDIR:-/tmp}/auroraia/agi_daemon.log")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = f.read()
            if "Traceback (most recent call last)" in logs or "ERREUR CRITIQUE AGI" in logs:
                logging.error("[AUTO-HEALING] Un crash précédent a été détecté au démarrage.")
                # L'AGI s'injecte le crash comme première tâche pour l'analyser et l'encoder dans sa mémoire
                last_crash = logs[-2000:] # Prend les 2000 derniers caractères (le traceback)
                asyncio.create_task(brain.swarm.delegate(f"AUTO-DIAGNOSTIC CRITIQUE : Analyse ce crash précédent et empêche sa reproduction : {last_crash}"))
                
                # Nettoie le log pour ne pas re-diagnostiquer en boucle
                with open(log_file, 'w') as fw:
                    fw.write("--- Crash Log Analysé et Purgé par l'AGI ---
")


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

async def simulate_client():
    """Simule un client distant (ex: le CLI) qui envoie une requête complexe au vrai cerveau."""
    await asyncio.sleep(2)
    # Le CLI envoie juste un événement sur le réseau (ici simulé via le bus)
    await global_bus.publish("client.request", {
        "client_id": "remote-cli-01",
        "prompt": "Fais un audit de sécurité de l'infrastructure réseau"
    })

async def main():
    brain = AGICortex()
    
    # Activation de l'auto-guérison
    check_for_previous_crashes(brain)

    
    # Écoute des réponses pour le client simulé
    async def on_response(data):
        print(f"\n[CLIENT CLI] A reçu la réponse finale du cerveau AGI :\n{data}\n")
        
    global_bus.subscribe("server.response.remote-cli-01", on_response)
    
    # Lancement du cerveau et de la simulation client
    await asyncio.gather(
        brain.run_continuous_loop(),
        simulate_client()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt du Cerveau AGI.")
