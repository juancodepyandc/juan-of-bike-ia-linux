import unittest
import asyncio
from agi_core.bus import AsyncEventBus

class TestAsyncEventBus(unittest.IsolatedAsyncioTestCase):
    async def test_bus_local_subscribe_publish(self):
        bus = AsyncEventBus()
        received = []

        async def handler(payload):
            received.append(payload)

        bus.subscribe("test.event", handler)
        await bus.publish("test.event", {"hello": "aurora"})
        await asyncio.sleep(0.05)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["hello"], "aurora")

    async def test_bus_pattern_dispatch(self):
        bus = AsyncEventBus()
        rec_a = []
        rec_b = []

        bus.subscribe("topic.a", lambda p: rec_a.append(p))
        bus.subscribe("topic.b", lambda p: rec_b.append(p))

        await bus.publish("topic.a", {"val": 1})
        await bus.publish("topic.b", {"val": 2})
        await asyncio.sleep(0.05)

        self.assertEqual(len(rec_a), 1)
        self.assertEqual(rec_a[0]["val"], 1)
        self.assertEqual(len(rec_b), 1)
        self.assertEqual(rec_b[0]["val"], 2)

if __name__ == "__main__":
    unittest.main()
