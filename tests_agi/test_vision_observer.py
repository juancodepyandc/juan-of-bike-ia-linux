"""Vision transport contracts with an HTTP fixture; no model quality claims."""
import asyncio
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import threading
import unittest

from PIL import Image
from agi_core.llm_gateway import LLMGateway
from agi_core.vision_observer import inspect_image_bytes, validate_visual_interpretation


class VisionServer(BaseHTTPRequestHandler):
    requests = []

    def send_json(self, value):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_GET(self):
        self.send_json({"models": [{"name": "ordinary", "size": 1}, {"name": "visual", "size": 2}, {"name": "large-visual", "size": 3}]})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.requests.append((self.path, payload))
        if self.path == "/api/show":
            self.send_json({"capabilities": ["completion"] + (["vision"] if "visual" in payload["model"] else [])})
        elif self.path == "/api/chat":
            image = payload["messages"][1]["images"][0]
            self.server.observed_image = base64.b64decode(image)
            answer = {"answer": "Fixture interpretation", "visible_text": [], "targets": [], "uncertainties": []}
            self.send_json({"message": {"content": json.dumps(answer)}, "done": True,
                            "eval_count": 8, "eval_duration": 1000000000})

    def log_message(self, *args):
        pass


class VisionObservationContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        VisionServer.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), VisionServer)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.gateway = LLMGateway(f"http://127.0.0.1:{self.server.server_port}", context_tokens=8192)
        image = io.BytesIO()
        Image.new("RGB", (16, 16)).save(image, "PNG")
        self.raw = image.getvalue()

    async def asyncTearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    async def test_actual_image_channel_capability_selection_and_metrics(self):
        result = await inspect_image_bytes(self.raw, "Describe visible content", gateway=self.gateway)
        self.assertEqual(self.server.observed_image, self.raw)
        self.assertEqual(result["model"], "visual")
        self.assertEqual(result["image"]["width"], 16)
        self.assertEqual(result["metrics"]["eval_count"], 8)
        request = next(payload for path, payload in VisionServer.requests if path == "/api/chat")
        self.assertNotIn(base64.b64encode(self.raw).decode(), request["messages"][1]["content"])
        self.assertIs(request["think"], False)

    async def test_explicit_incapable_or_missing_model_is_never_silently_replaced(self):
        for model in ("ordinary", "not-installed"):
            with self.assertRaises(ValueError):
                await inspect_image_bytes(self.raw, "Describe content", model=model, gateway=self.gateway)
        self.assertFalse(any(path == "/api/chat" for path, _ in VisionServer.requests))

    async def test_invalid_image_or_question_cannot_submit_inference(self):
        with self.assertRaises(ValueError):
            await inspect_image_bytes(b"not an image", "Describe content", gateway=self.gateway)
        with self.assertRaises(ValueError):
            await inspect_image_bytes(self.raw, "", gateway=self.gateway)
        self.assertEqual(VisionServer.requests, [])

    def test_unbounded_nonfinite_or_invalid_point_interpretation_is_rejected(self):
        base = {"answer": "Observed", "visible_text": [], "targets": [], "uncertainties": []}
        for coordinate in (float("nan"), float("inf"), -0.1, 1.1, True):
            with self.assertRaises(ValueError):
                validate_visual_interpretation({**base, "targets": [{"label": "target", "x": coordinate, "y": .5}]})
