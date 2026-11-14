"""Real pipe/process contract tests, including strict MCP lifecycle and lost effects."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from agi_core.mcp_transport import call_stdio, close_mcp_sessions


class TransportSessions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.script = Path(__file__).with_name("fixtures") / "mcp_stateful_server.py"
        self.server = {"command": sys.executable, "args": [str(self.script)], "persistent": True}

    def tearDown(self):
        close_mcp_sessions()
        self.temp.cleanup()

    def call(self, name="counter", **kw):
        return call_stdio(self.server, "tools/call", {"name": name}, cwd=str(self.root), **kw)

    def test_initialized_session_reuses_process_and_keeps_state(self):
        self.assertEqual(self.call()[0]["result"]["counter"], 1)
        self.assertEqual(self.call()[0]["result"]["counter"], 2)

    def test_default_one_shot_preserved(self):
        self.server.pop("persistent")
        self.assertEqual(self.call()[0]["result"]["counter"], 1)
        self.assertEqual(self.call()[0]["result"]["counter"], 1)

    def test_uncertain_effect_is_not_replayed_or_silently_reconnected(self):
        started = time.monotonic()
        result, error = self.call("uncertain", timeout=.3)
        self.assertIsNone(result)
        self.assertIn("inspect", error)
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual((self.root / "effect.txt").read_text(), "1")
        self.assertIsNone(self.call()[0])
        self.assertEqual((self.root / "effect.txt").read_text(), "1")

    def test_message_bound(self):
        self.assertIsNone(self.call("flood", timeout=2)[0])

    def test_workspace_isolates_process(self):
        other = self.root / "other"
        other.mkdir()
        self.call()
        self.call()
        result, error = call_stdio(self.server, "tools/call", {}, cwd=str(other))
        self.assertIsNone(error)
        self.assertEqual(result["result"]["counter"], 1)
