"""HTTP authorization is tested independently of Chromium and the running bridge."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from flask import Flask

PATH = Path(__file__).resolve().parents[1] / "application/routes/web_action_bp_routes.py"
spec = importlib.util.spec_from_file_location("browser_api_contract", PATH)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class BrowserApiAccess(unittest.TestCase):
    def setUp(self):
        self.bridge = ModuleType("bridge_server")
        self.bridge.WORKSPACE = str(PATH.parents[1])
        self.bridge._request_is_local_loopback = lambda: False
        self.bridge._ext_auth = lambda: (False, None, "unauthorized")
        self.modules = patch.dict(sys.modules, {"bridge_server": self.bridge})
        self.modules.start()
        app = Flask(__name__)
        app.register_blueprint(api.web_action_bp)
        self.client = app.test_client()
        self.runtime = patch.object(api, "browser_action", return_value={"ok": True})
        self.calls = self.runtime.start()
        self.identity = patch("application.device_pairing.request_identity", return_value="device:owner")
        self.identity.start()

    def tearDown(self):
        self.identity.stop()
        self.runtime.stop()
        self.modules.stop()

    def test_public_and_safe_callers_cannot_launch_browser(self):
        self.assertEqual(self.client.post("/api/web/action", json={"action": "open"}).status_code, 403)
        self.bridge._ext_auth = lambda: (True, {"permissions": "SAFE"}, None)
        self.assertEqual(self.client.post("/api/web/action", json={"action": "open"}).status_code, 403)
        self.calls.assert_not_called()

    def test_authorized_owner_is_derived_on_server(self):
        self.bridge._ext_auth = lambda: (True, {"id": "owner"}, None)
        response = self.client.post("/api/web/action", json={"action": "open", "url": "https://example.invalid", "owner": "forged"})
        self.assertEqual(response.status_code, 200)
        import hashlib
        self.assertEqual(self.calls.call_args.kwargs["owner"], hashlib.sha256(b"device:owner").hexdigest())

    def test_invalid_json_does_not_launch_browser(self):
        self.bridge._ext_auth = lambda: (True, {"id": "owner"}, None)
        self.assertEqual(self.client.post("/api/web/action", json=[]).status_code, 400)
        self.calls.assert_not_called()
