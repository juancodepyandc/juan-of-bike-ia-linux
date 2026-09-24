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
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    log_file = os.path.join(tmpdir, "auroraia/agi_daemon.log")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = f.read()
            if "Traceback (most recent call last)" in logs or "ERREUR CRITIQUE AGI" in logs:
                logging.error("[AUTO-HEALING] Un crash précédent a été détecté au démarrage.")
                last_crash = logs[-2000:]
                
                async def _heal_and_learn():
                    result = await brain.swarm.delegate(f"AUTO-DIAGNOSTIC CRITIQUE : Analyse ce crash précédent et empêche sa reproduction : {last_crash}")
                    if brain.memory:
                        await brain.memory.embed_experience(
                            context=f"Crash système détecté:\n{last_crash}",
                            outcome=f"Analyse interne (Auto-healing):\n{result}",
                            metadata={"type": "auto_healing"}
                        )
                task = asyncio.create_task(_heal_and_learn())
                brain.background_task = task
                task.add_done_callback(lambda t: None if t.cancelled() else logging.error(f"[AUTO-HEALING] Echec: {t.exception()}") if t.exception() else logging.info("[AUTO-HEALING] Diagnostic terminé et encodé."))
                
                # Nettoie le log pour ne pas re-diagnostiquer en boucle
                with open(log_file, 'w') as fw:
                    fw.write("--- Crash Log Analysé et Purgé par l'AGI ---\n")


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

async def main():
    brain = AGICortex()
    
    # Activation de l'auto-guérison
    check_for_previous_crashes(brain)

    logger = logging.getLogger("AuroraAGI")
    logger.info("Démarrage du système nerveux (IPC Bus)...")
    missions = brain.active_missions

    async def execute_mission(payload):
        mission_id = payload["mission_id"]
        try:
            await brain.stop_background_work()
            await brain.swarm.run_mission(
                mission_id=mission_id, request_text=payload.get("request"),
                workspace=payload.get("workspace"), model=payload.get("model"),
                permissions=payload.get("permissions"), memory_module=brain.memory,
                history=payload.get("history"),
            )
        except asyncio.CancelledError:
            await global_bus.publish("mission.event", {
                "mission_id": mission_id,
                "event": {"type": "mission_complete", "stopped": True, "result": "Mission arrêtée."},
            })
            raise
        except Exception as exc:
            logger.exception("Mission failed: %s", mission_id)
            await global_bus.publish("mission.event", {
                "mission_id": mission_id, "event": {"type": "error", "message": str(exc)},
            })
        finally:
            missions.pop(mission_id, None)
    
    async def on_mission_start(payload):
        logger.info(f"[DAEMON] Nouvelle mission reçue : {payload.get('mission_id')}")
        mission_id = payload.get("mission_id")
        if mission_id and mission_id not in missions:
            missions[mission_id] = asyncio.create_task(execute_mission(payload))

    async def on_mission_stop(payload):
        task = missions.get(payload.get("mission_id"))
        if task is not None and not task.done() and not task.cancelling():
            task.cancel()
        
    global_bus.subscribe("mission.start", on_mission_start)
    global_bus.subscribe("mission.stop", on_mission_stop)
    
    # Lancement du bus IPC et de la boucle du cerveau
    await asyncio.gather(
        global_bus.start_server(),
        brain.run_continuous_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt du Cerveau AGI.")
    except Exception as e:
        print(f"\n[CRITIQUE] Le daemon AGI a eu un crash inattendu: {e}")
