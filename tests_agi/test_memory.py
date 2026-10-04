import unittest
import tempfile
import os
import sqlite3
from unittest.mock import patch
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
        await memory.embed_experience(
            context="Fixing Vite supervisor PATH issue",
            outcome="Vite now starts automatically on port 1420",
            metadata={"test": True}
        )
        retrieved = await memory.query_experience("Vite supervisor", n_results=1)
        self.assertTrue(len(retrieved) > 0)
        self.assertIn("1420", retrieved[0])

    async def test_sqlite_handles_are_released_after_every_operation(self):
        opened = []
        connect = sqlite3.connect
        def tracked(*args,**kwargs):
            connection = connect(*args,**kwargs)
            opened.append(connection)
            return connection
        with patch('agi_core.memory.sqlite3.connect',tracked),patch.dict('sys.modules',{'chromadb':None}):
            memory = OmniscientMemory(db_path=self.tmp_dir.name)
            await memory.embed_experience('resource release','Connection closed after commit')
            self.assertTrue(await memory.query_experience('resource'))
        self.assertGreaterEqual(len(opened),3)
        for connection in opened:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')
        memory.sqlite_path.unlink()  # Also proves release on Windows, without waiting for GC.

if __name__ == "__main__":
    unittest.main()
