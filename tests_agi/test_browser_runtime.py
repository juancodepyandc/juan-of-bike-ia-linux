"""Real Chromium integration on a local HTTP fixture; no model or external website."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest

from agi_core.browser_runtime import BrowserRuntime, browser_error_diagnostic
from agi_core.mcp_transport import call_stdio, close_mcp_sessions


class Site(BaseHTTPRequestHandler):
    def do_GET(self):
        page = '''<!doctype html><title>Browser contract</title>
        <label>Project name<input id="name"></label><input type="password" value="private-input">
        <button onclick="document.querySelector('output').textContent='Saved: '+document.querySelector('#name').value; localStorage.saved=document.querySelector('#name').value">Save</button>
        <output></output><a href="/next">Next page</a>'''
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode())

    def log_message(self, *args):
        pass


class BrowserDiagnostics(unittest.TestCase):
    def test_long_launch_error_preserves_cause_after_flags(self):
        error = "Browser launch failed: " + "argument " * 1000 + "missing shared library at launch"
        diagnostic = browser_error_diagnostic(error)
        self.assertIn("Browser launch failed", diagnostic)
        self.assertIn("missing shared library at launch", diagnostic)
        self.assertLess(len(diagnostic), 2100)


class BrowserContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), Site)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.http.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    def setUp(self):
        self.runtime = BrowserRuntime(timeout_ms=3000)

    def tearDown(self):
        self.runtime.close()
        close_mcp_sessions()

    def opened(self):
        result = self.runtime.call({"action": "open", "url": self.url})
        self.assertTrue(result["ok"], result)
        return result

    def act(self, observation, action, **args):
        return self.runtime.call({"action": action, "session_id": observation["session_id"],
                                  "observation_id": observation["observation_id"], **args})

    def test_observe_fill_click_and_screenshot_preserve_state(self):
        observed = self.opened()
        self.assertNotIn("private-input", json.dumps(observed))
        target = next(e["ref"] for e in observed["elements"] if e["name"] == "Project name")
        filled = self.act(observed, "fill", ref=target, value="Aurora test")
        self.assertTrue(filled["ok"], filled)
        button = next(e["ref"] for e in filled["elements"] if e["name"] == "Save")
        saved = self.act(filled, "click", ref=button)
        self.assertTrue(saved["ok"], saved)
        self.assertIn("Saved: Aurora test", saved["text"])
        screenshot = self.act(saved, "screenshot")
        self.assertTrue(screenshot["screenshot"]["data"].startswith("iVBOR"))

    def test_stale_observation_cannot_mutate(self):
        observed = self.opened()
        fresh = self.act(observed, "observe")
        button = next(e["ref"] for e in observed["elements"] if e["name"] == "Save")
        stale = self.act(observed, "click", ref=button)
        self.assertFalse(stale["ok"])
        self.assertIn("Stale", stale["error"])
        self.assertNotEqual(fresh["observation_id"], stale["observation_id"])

    def test_callers_and_contexts_are_isolated(self):
        observed = self.opened()
        stolen = self.runtime.call({"action": "observe", "session_id": observed["session_id"]}, owner="other")
        self.assertFalse(stolen["ok"])
        self.assertNotIn("text", stolen)
        second = self.opened()
        self.assertNotEqual(observed["session_id"], second["session_id"])
        self.assertNotIn("Saved:", second["text"])

    def test_non_web_url_and_session_capacity(self):
        self.assertFalse(self.runtime.call({"action": "open", "url": "file:///etc/passwd"})["ok"])
        self.runtime.max_sessions = 1
        observed = self.opened()
        self.assertFalse(self.runtime.call({"action": "open", "url": self.url})["ok"])
        self.assertTrue(self.act(observed, "close")["ok"])
        self.opened()

    def test_point_action_uses_measured_bounds_and_refuses_changed_pixels(self):
        observed = self.opened()
        screenshot = self.act(observed, "screenshot")
        button = next(e for e in screenshot["elements"] if e["name"] == "Save")
        bounds, viewport = button["bounds"], screenshot["capture"]["viewport"]
        x = (bounds["x"] + bounds["width"] / 2) / viewport["width"]
        y = (bounds["y"] + bounds["height"] / 2) / viewport["height"]
        clicked = self.act(screenshot, "click_point", x=x, y=y, image_sha256=screenshot["capture"]["sha256"])
        self.assertTrue(clicked["ok"], clicked)
        self.assertIn("Saved:", clicked["text"])
        fresh = self.act(clicked, "screenshot")
        rejected = self.act(fresh, "click_point", x=x, y=y, image_sha256="not-the-observed-image")
        self.assertFalse(rejected["ok"])

    def test_point_action_cannot_run_without_observed_image_or_with_invalid_position(self):
        observed = self.opened()
        self.assertFalse(self.act(observed, "click_point", x=.5, y=.5, image_sha256="invented")["ok"])
        fresh = self.act(observed, "screenshot")
        self.assertFalse(self.act(fresh, "click_point", x=float("nan"), y=.5, image_sha256=fresh["capture"]["sha256"])["ok"])

    def test_real_mcp_browser_observations_across_calls(self):
        server = {"command": sys.executable, "args": [str(Path(__file__).resolve().parents[1] / "mcp/cowork/server.py")], "persistent": True}
        def call(args, *, raw=False):
            response, error = call_stdio(server, "tools/call", {"name": "mcp_browser_action", "arguments": args}, timeout=15)
            self.assertIsNone(error)
            self.assertFalse(response["result"]["isError"], response)
            return response if raw else response["result"]["structuredContent"]
        opened = call({"action": "open", "url": self.url})
        target = next(e["ref"] for e in opened["elements"] if e["name"] == "Project name")
        filled = call({"action": "fill", "session_id": opened["session_id"], "observation_id": opened["observation_id"], "ref": target, "value": "Through MCP"})
        button = next(e["ref"] for e in filled["elements"] if e["name"] == "Save")
        saved = call({"action": "click", "session_id": filled["session_id"], "observation_id": filled["observation_id"], "ref": button})
        self.assertIn("Saved: Through MCP", saved["text"])
        screenshot = call({"action": "screenshot", "session_id": opened["session_id"]}, raw=True)
        images = [block for block in screenshot["result"]["content"] if block["type"] == "image"]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["mimeType"], "image/png")
        self.assertTrue(images[0]["data"].startswith("iVBOR"))
        self.assertNotIn("screenshot", screenshot["result"]["structuredContent"])
        call({"action": "close", "session_id": opened["session_id"]})
