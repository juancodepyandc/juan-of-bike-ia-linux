#!/usr/bin/env python3
"""
Point d'entrée du Démon AGI Aurora (Le vrai cerveau backend).
Doit tourner en permanence avec bridge_server.py.
"""
import asyncio
import logging
import os
from uuid import uuid4
from agi_core.mission_store import MissionStore
from agi_core.runtime_policy import positive_env
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
                
                # Preserve the original crash log; a recommendation is not a repair.


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

async def main():
    brain = AGICortex()
    
    # Background diagnostics are opt-in; no inference unrelated to an active request.
    if os.environ.get("AURORA_BACKGROUND_ANALYSIS") == "1":
        check_for_previous_crashes(brain)

    logger = logging.getLogger("AuroraAGI")
    logger.info("Démarrage du système nerveux (IPC Bus)...")
    missions = brain.active_missions

    store = MissionStore()
    owner = uuid4().hex
    slots = asyncio.Semaphore(positive_env("AURORA_CONCURRENT_MISSIONS", 1))
    cancelling = set()

    def cancel(task):
        # Python 3.10 has no Task.cancelling(); also preserve cleanup on repeated stops.
        if not task.done() and task not in cancelling:
            cancelling.add(task)
            task.cancel()

    async def publish(mid, kind, **data):
        event = {"type":kind,"event_id":uuid4().hex,**data}
        await asyncio.to_thread(store.append,mid,event)
        await global_bus.publish("mission.event", {"mission_id":mid,"event":event})

    async def execute_mission(payload):
        mission_id = payload["mission_id"]
        lease_owner = owner + '-' + uuid4().hex
        task = asyncio.current_task()
        heartbeat = None
        try:
            if not await asyncio.to_thread(store.claim,mission_id,lease_owner):
                return
            async def renew():
                while True:
                    await asyncio.sleep(10)
                    state = await asyncio.to_thread(store.get,mission_id)
                    if state and state['status'] == 'stopping':
                        cancel(task)
                        return
                    if not await asyncio.to_thread(store.renew,mission_id,lease_owner):
                        if not state or state['status'] != 'completed':
                            cancel(task)
                        return
            heartbeat = asyncio.create_task(renew())
            async with slots:
                await brain.stop_background_work()
                await brain.swarm.run_mission(
                    mission_id=mission_id, request_text=payload.get("request"),
                    workspace=payload.get("workspace"), model=payload.get("model"),
                    permissions=payload.get("permissions"), memory_module=brain.memory,
                    history=payload.get("history"), store=store, lease_owner=lease_owner)
        except asyncio.CancelledError:
            await publish(mission_id,"mission_complete",lease_owner=lease_owner,stopped=True,result="Mission arrêtée ; état conservé pour reprise.")
            raise
        except Exception as exc:
            logger.exception("Mission failed: %s",mission_id)
            await publish(mission_id,"error",lease_owner=lease_owner,message=str(exc))
        finally:
            if heartbeat:
                heartbeat.cancel()
                await asyncio.gather(heartbeat,return_exceptions=True)
            missions.pop(mission_id,None)
            cancelling.discard(task)

    async def on_mission_start(payload):
        mission_id = payload.get("mission_id")
        if mission_id:
            # Execute the accepted durable payload, never a conflicting replay.
            accepted = await asyncio.to_thread(store.get,mission_id)
            if accepted:
                old = missions.get(mission_id)
                if old is not None:
                    if accepted['status'] != 'planning' or accepted['owner'] is not None:
                        return
                    cancel(old)
                    await asyncio.gather(old,return_exceptions=True)
                missions[mission_id] = asyncio.create_task(execute_mission({"mission_id":mission_id,**accepted['payload']}))

    async def on_mission_stop(payload):
        task = missions.get(payload.get("mission_id"))
        if task is not None and not task.done():
            cancel(task)
        
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
        raise SystemExit(1)
