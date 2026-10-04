import asyncio
import logging
import json
from typing import Callable, Dict, List, Any
import socket
import threading
import os

logger = logging.getLogger("AuroraAGI.Bus")
BUS_PORT = 3002

class AsyncEventBus:
    """
    Système nerveux central du Backend Aurora.
    Implémentation IPC via TCP (Pub/Sub) pour la communication Bridge <-> Daemon.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._clients = set()

    async def start_server(self):
        """Démarre le serveur IPC central (lancé uniquement par le Daemon AGI)."""
        server = await asyncio.start_server(self._handle_client, '127.0.0.1', BUS_PORT,
                                            limit=int(os.environ.get('AURORA_BUS_LINE_BYTES', str(1024*1024))))
        logger.info(f"[BUS] Serveur IPC démarré sur le port {BUS_PORT}")
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader, writer):
        self._clients.add(writer)
        peer = writer.get_extra_info('peername')
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                
                try:
                    msg = json.loads(line.decode().strip())
                except json.JSONDecodeError:
                    continue
                
                action = msg.get("action")
                logger.debug("[BUS] Action reçue: %s", action)
                if action == "health":
                    reply = {"ok": True, "protocol": 1,
                             "mission_ready": bool(self._subscribers.get("mission.start"))}
                    writer.write((json.dumps(reply) + "\n").encode())
                    await writer.drain()
                    continue
                if action == "publish":
                    # Relai local aux subscribers asynchrones du Daemon
                    event_type = msg.get("event_type")
                    payload = msg.get("payload")
                    logger.info(f"[BUS] Local publish event: {event_type}")
                    await self._local_publish(event_type, payload)
                    
                    # Relai réseau aux autres clients TCP connectés (ex: bridge Flask SSE)
                    # On re-broadcast (simplifié) à tout le monde. Les clients filtrent.
                    broadcast_msg = json.dumps({"event_type": event_type, "payload": payload}) + "\n"
                    for w in list(self._clients):
                        if w != writer:
                            try:
                                w.write(broadcast_msg.encode())
                                await w.drain()
                            except Exception:
                                self._clients.discard(w)
                
                elif action == "subscribe":
                    # Le client informe qu'il écoute (utile pour log/debug, le filtrage est côté client pr simplifier)
                    pass

        except Exception as e:
            logger.debug(f"[BUS] Erreur client IPC {peer}: {e}")
        finally:
            self._clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def subscribe(self, event_pattern: str, callback: Callable):
        """Souscription locale (dans le même process)."""
        if event_pattern not in self._subscribers:
            self._subscribers[event_pattern] = []
        self._subscribers[event_pattern].append(callback)
        logger.debug(f"[BUS] Node local connecté sur: {event_pattern}")

    async def _local_publish(self, event_type: str, payload: Any):
        logger.info(f"[BUS] self._subscribers = {list(self._subscribers.keys())}")
        if event_type in self._subscribers:
            for cb in self._subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.create_task(cb(payload)).add_done_callback(
                            lambda t: logger.error(f"[BUS] Task error: {t.exception()}")
                            if not t.cancelled() and t.exception() else None)
                    else:
                        asyncio.create_task(asyncio.to_thread(cb, payload))
                except Exception as e:
                    logger.error(f"[BUS] _local_publish error: {e}")

    async def publish(self, event_type: str, payload: Any):
        """Publication globale depuis le Daemon."""
        await self._local_publish(event_type, payload)
        broadcast_msg = json.dumps({"event_type": event_type, "payload": payload}) + "\n"
        for w in list(self._clients):
            try:
                w.write(broadcast_msg.encode())
                await w.drain()
            except Exception:
                self._clients.discard(w)

def publish_sync(event_type: str, payload: Any):
    """Publication synchrone depuis le Bridge Flask."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(('127.0.0.1', BUS_PORT))
            msg = json.dumps({"action": "publish", "event_type": event_type, "payload": payload}) + "\n"
            s.sendall(msg.encode())
    except Exception as e:
        logger.warning(f"[BUS] Échec de la publication synchrone: {e}")

global_bus = AsyncEventBus()


def probe_sync(timeout: float = 2.0, port: int = BUS_PORT) -> dict:
    """Require a protocol reply and a mission subscriber, not only an open port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
            connection.sendall(b'{"action":"health"}\n')
            with connection.makefile("rb") as stream:
                line = stream.readline(4097)
            if len(line) > 4096 or not line.endswith(b"\n"):
                raise ValueError("Invalid health response")
            reply = json.loads(line)
            if not isinstance(reply, dict) or reply.get("protocol") != 1:
                raise ValueError("Unknown bus protocol")
            return {"ok": reply.get("ok") is True,
                    "mission_ready": reply.get("mission_ready") is True}
    except (OSError, ValueError):
        return {"ok": False, "mission_ready": False}
