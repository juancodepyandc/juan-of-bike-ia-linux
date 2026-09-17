import asyncio
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger("AuroraAGI.Bus")

class AsyncEventBus:
    """Système nerveux central du Backend Aurora."""
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_pattern: str, callback: Callable):
        if event_pattern not in self._subscribers:
            self._subscribers[event_pattern] = []
        self._subscribers[event_pattern].append(callback)
        logger.debug(f"[BUS] Node connecté sur: {event_pattern}")

    async def publish(self, event_type: str, payload: Any):
        if event_type in self._subscribers:
            tasks = [
                asyncio.create_task(cb(payload)) if asyncio.iscoroutinefunction(cb) else asyncio.to_thread(cb, payload)
                for cb in self._subscribers[event_type]
            ]
            if tasks:
                await asyncio.gather(*tasks)

global_bus = AsyncEventBus()
