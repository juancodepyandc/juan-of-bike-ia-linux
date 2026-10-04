import unittest
import tempfile
import os
from agi_core.memory import OmniscientMemory

class TestOmniscientMemory(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    async def test_memory_init_and_query(self):
        memory = OmniscientMemory(db_path=self.tmp_dir.name)
        # Should initialize gracefully
        self.assertIsNotNone(memory.db_path)

        # Test query on empty/volatile memory
        results = await memory.query_experience("Test Situation", n_results=1)
        self.assertIsInstance(results, list)

    async def test_memory_embed_and_retrieve(self):
        memory = OmniscientMemory(db_path=self.tmp_dir.name)
        if memory.collection is not None:
            await memory.embed_experience(
                context="Fixing Vite supervisor PATH issue",
                outcome="Vite now starts automatically on port 1420",
                metadata={"test": True}
            )
            retrieved = await memory.query_experience("Vite supervisor", n_results=1)
            self.assertTrue(len(retrieved) > 0)
            self.assertIn("1420", retrieved[0])

if __name__ == "__main__":
    unittest.main()
