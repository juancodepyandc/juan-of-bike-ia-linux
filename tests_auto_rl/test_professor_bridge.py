"""Bridge routes of the professor autopilot (Flask test client; the runner process is not started).

Skipped where Flask is not installed: the bridge's own environment has it.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import flask
except ImportError:                                      # pragma: no cover - environments without the bridge
    flask = None

from auto_rl.professor import autopilot, bridge_routes


@unittest.skipIf(flask is None, "Flask is not installed in this environment")
class Routes(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.patches = [patch.object(autopilot, "AUTOPILOT", root), patch.object(autopilot, "STATE_FILE", root / "state.json"),
                        patch.object(autopilot, "STOP_FILE", root / "STOP"), patch.object(autopilot, "LOG_FILE", root / "runner.log"),
                        patch.object(bridge_routes, "missing_requirements", lambda: [])]
        for item in self.patches:
            item.start()
        self.device = {"ok": True}
        app = flask.Flask("test")
        bridge_routes.register_routes(app, allowed=lambda: self.device["ok"])
        self.client = app.test_client()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.folder.cleanup()

    def test_a_public_request_without_this_device_is_refused_even_for_reading(self):
        self.device["ok"] = False
        for method, path in (("get", "/api/professor/autopilot"), ("post", "/api/professor/autopilot/start"),
                             ("post", "/api/professor/autopilot/stop")):
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()["error"], "forbidden_public")      # the interface opens the pairing dialog

    def test_start_spawns_one_runner_and_a_second_start_is_refused(self):
        with patch.object(bridge_routes, "spawn_runner", return_value=4242) as spawn:
            response = self.client.post("/api/professor/autopilot/start", json={"activate": False})
            self.assertEqual(response.get_json(), {"started": True, "pid": 4242})
            spawn.assert_called_once_with(activate=False)
            state = autopilot.load()
            state["runner"] = {"pid": 4242, "heartbeat": autopilot.time.time(), "busy": None}
            autopilot.save(state)
            self.assertEqual(self.client.post("/api/professor/autopilot/start").status_code, 409)
            self.assertEqual(spawn.call_count, 1)

    def test_cross_site_actions_are_refused(self):
        response = self.client.post("/api/professor/autopilot/stop", headers={"Origin": "https://evil.example"})
        self.assertEqual(response.status_code, 403)

    def test_status_stop_and_resume(self):
        status = self.client.get("/api/professor/autopilot").get_json()
        self.assertTrue(status["supported"])
        self.assertFalse(status["running"])
        self.assertEqual(self.client.post("/api/professor/autopilot/stop").get_json(), {"stopping": True})
        self.assertTrue(autopilot.STOP_FILE.exists())
        self.assertEqual(self.client.post("/api/professor/autopilot/resume", json={"student": "nope"}).status_code, 400)
        self.assertEqual(self.client.post("/api/professor/autopilot/resume", json={"student": "qwen2.5:7b"}).get_json(),
                         {"resumed": "qwen2.5:7b"})

    def test_a_pc_without_kaggle_reports_why_and_cannot_start(self):
        with patch.object(bridge_routes, "missing_requirements", lambda: ["identifiants Kaggle absents"]):
            status = self.client.get("/api/professor/autopilot").get_json()
            self.assertFalse(status["supported"])
            self.assertEqual(status["error"], "identifiants Kaggle absents")
            self.assertEqual(self.client.post("/api/professor/autopilot/start").status_code, 503)


if __name__ == "__main__":
    unittest.main()
