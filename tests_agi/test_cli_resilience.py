"""Exercise the real CLI blueprint without a daemon, models, or user state."""

from concurrent.futures import ThreadPoolExecutor
import importlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from flask import Flask


class CliResilienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": cls.directory.name}), \
                mock.patch("threading.Thread.start"):
            cls.routes = importlib.import_module("routes.cli_bp_routes")
        cls.app = Flask(__name__)
        cls.app.register_blueprint(cls.routes.cli_bp)

    def setUp(self):
        self.routes._CLI_MISSIONS.clear()
        self.client = self.app.test_client()
        self.headers = {"Authorization": "Bearer test-key"}
        bridge = importlib.import_module("bridge_server")
        self.record = {"hash": bridge._ext_hash("test-key"), "label": "test"}
        store = {"keys": [self.record]}
        for target in (bridge, self.routes):
            patch = mock.patch.object(target, "_ext_load", return_value=store)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(self.routes, "_ext_save")
        self.save = patch.start()
        self.addCleanup(patch.stop)

    def mission(self, status="completed"):
        mission = {
            "id": "fixture", "status": status, "started_at": time.time(),
            "finished_at": None, "steps": [], "errors": [],
            "events": [{"type": "token", "content": "un"},
                       {"type": "token", "content": "deux"},
                       {"type": "mission_complete", "result": "undeux"}],
        }
        self.routes._CLI_MISSIONS["fixture"] = mission
        return mission

    def test_auth_rejects_missing_invalid_and_revoked_keys(self):
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get("/api/cli/version", headers=headers).status_code, 401)
        self.record["revoked"] = True
        self.assertEqual(self.client.get("/api/cli/version", headers=self.headers).status_code, 401)

    def test_every_cli_endpoint_requires_authority(self):
        checked = 0
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint.startswith("cli_bp."):
                path = rule.rule
                for argument in rule.arguments:
                    path = path.replace(f"<{argument}>", "fixture")
                method = next(m for m in sorted(rule.methods) if m not in ("HEAD", "OPTIONS"))
                with self.subTest(path=path, method=method):
                    self.assertEqual(self.client.open(path, method=method).status_code, 401)
                checked += 1
        self.assertGreater(checked, 30)

    def test_valid_auth_sets_key_record(self):
        response = self.client.post("/api/cli/auth", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["label"], "test")

    def test_registration_requires_existing_authority(self):
        response = self.client.post("/api/cli/register", json={"client_key": "new-key"})
        self.assertEqual(response.status_code, 401)
        self.save.assert_not_called()
        response = self.client.post("/api/cli/register", headers=self.headers,
                                    json={"client_key": "new-key", "device_name": "fixture"})
        self.assertEqual(response.status_code, 200)
        self.save.assert_called_once()

    def test_malformed_mission_body_is_rejected_without_dispatch(self):
        for body in (["request"], {"request": ["wrong"]}, {"request": "x", "permissions": "root"}):
            with self.subTest(body=body), mock.patch.object(self.routes, "_cli_publish_ipc") as publish:
                response = self.client.post("/api/cli/mission/start", headers=self.headers, json=body)
                self.assertEqual(response.status_code, 400)
                publish.assert_not_called()

    def test_unavailable_daemon_does_not_report_planning(self):
        with mock.patch.object(self.routes, "_cli_publish_ipc", return_value=False):
            response = self.client.post("/api/cli/mission/start", headers=self.headers,
                                        json={"request": "fixture", "model": "fixture"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self.routes._CLI_MISSIONS)

    def test_reconnect_replays_only_events_after_cursor(self):
        self.mission()
        response = self.client.get("/api/cli/mission/fixture/stream",
                                   headers={**self.headers, "Last-Event-ID": "1"})
        body = response.get_data(as_text=True)
        self.assertNotIn('"content": "un"', body)
        self.assertIn("id: 2\n", body)
        self.assertIn("id: 3\n", body)
        self.assertEqual(sum(line.startswith("data:") for line in body.splitlines()), 2)

    def test_invalid_and_future_cursors_fail_before_streaming(self):
        self.mission()
        for cursor, status in (("-1", 400), ("bad", 400), ("4", 409)):
            with self.subTest(cursor=cursor):
                response = self.client.get("/api/cli/mission/fixture/stream",
                                           headers={**self.headers, "Last-Event-ID": cursor})
                self.assertEqual(response.status_code, status)

    def test_terminal_cursor_has_no_duplicate_payload(self):
        self.mission()
        response = self.client.get("/api/cli/mission/fixture/stream",
                                   headers={**self.headers, "Last-Event-ID": "3"})
        self.assertNotIn("data:", response.get_data(as_text=True))

    def test_event_error_is_terminal_and_late_tokens_are_ignored(self):
        mission = self.mission(status="running")
        mission["events"] = []
        for event in ({"type": "error", "error": "fixture failure"},
                      {"type": "token", "content": "late"}):
            self.routes._cli_record_mission_event({"mission_id": "fixture", "event": event})
        self.assertEqual(mission["status"], "failed")
        self.assertEqual(len(mission["events"]), 1)
        self.assertEqual(mission["errors"][0]["message"], "fixture failure")

    def test_parallel_subscribers_keep_independent_cursors(self):
        mission = self.mission()
        mission["events"] = [{"type": "token", "content": str(i)} for i in range(100)]
        mission["events"].append({"type": "mission_complete", "result": "fixture"})

        def read(cursor):
            with self.app.test_client() as client:
                response = client.get("/api/cli/mission/fixture/stream",
                                      headers={**self.headers, "Last-Event-ID": str(cursor)})
                return [int(line[4:]) for line in response.get_data(as_text=True).splitlines()
                        if line.startswith("id: ")]

        with ThreadPoolExecutor(max_workers=8) as pool:
            histories = list(pool.map(read, range(32)))
        for cursor, history in enumerate(histories):
            self.assertEqual(history, list(range(cursor + 1, 102)))

    def test_real_http_disconnect_resumes_without_loss_or_duplication(self):
        import httpx
        from werkzeug.serving import make_server

        remote = Path(__file__).resolve().parents[2] / "aurora-remote-cli"
        if not (remote / "aurora_cli/client.py").is_file():
            self.skipTest("cross-repository check requires the remote CLI checkout")
        sys.path.insert(0, str(remote))
        from aurora_cli.client import AuroraClient

        mission = self.mission()
        mission["events"] = [{"type": "token", "content": str(i)} for i in range(100)]
        mission["events"].append({"type": "mission_complete", "result": "fixture"})
        seen_cursors = []

        class InterruptedStream(httpx.SyncByteStream):
            def __init__(self, source):
                self.source = source

            def __iter__(self):
                buffer = b""
                for chunk in self.source:
                    buffer += chunk
                    if b"id: 2\n" in buffer:
                        yield buffer.split(b"id: 2\n")[0] + b"id: 2\ndata: {"
                        raise httpx.ReadError("injected disconnect after event 1")

            def close(self):
                self.source.close()

        class InterruptedTransport(httpx.HTTPTransport):
            def handle_request(self, request):
                seen_cursors.append(request.headers.get("Last-Event-ID"))
                response = super().handle_request(request)
                if len(seen_cursors) == 1:
                    response.stream = InterruptedStream(response.stream)
                return response

        server = make_server("127.0.0.1", 0, self.app, threaded=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with mock.patch("aurora_cli.config.load", return_value={}):
                client = AuroraClient(server_url=f"http://127.0.0.1:{server.server_port}", api_key="test-key")
            client._client.close()
            client._client = httpx.Client(base_url=client.server_url, headers=self.headers,
                                        transport=InterruptedTransport(), timeout=5)
            try:
                with mock.patch("aurora_cli.client.time.sleep"):
                    events = list(client.mission_stream("fixture"))
            finally:
                client.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        self.assertEqual(seen_cursors, ["0", "1"])
        self.assertEqual([e["content"] for e in events if e["type"] == "token"], [str(i) for i in range(100)])
        self.assertEqual(events[-1]["type"], "mission_complete")


if __name__ == "__main__":
    unittest.main()
