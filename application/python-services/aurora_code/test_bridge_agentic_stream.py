import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bridge_agentic_stream import PLAN_SCHEMA, normalize_plan, run_agentic_stream


def plan() -> dict:
    return {
        "schemaVersion": PLAN_SCHEMA,
        "projectType": "static_web",
        "summary": "Une application web complete generee fichier par fichier.",
        "stack": {},
        "files": [
            {"path": "index.html", "role": "entry", "language": "html", "required": True},
            {"path": "style.css", "role": "styles", "language": "css", "required": True},
        ],
        "generationOrder": ["index.html", "style.css"],
    }


class BridgeAgenticStreamTests(unittest.TestCase):
    def test_rejects_traversal_and_invalid_schema(self):
        candidate = plan()
        candidate["files"][0]["path"] = "../../etc/passwd"
        normalized, errors = normalize_plan(candidate)
        self.assertIsNone(normalized)
        self.assertIn("file_path_invalid_or_duplicate", errors)

    def test_runs_a_real_file_by_file_contract(self):
        events = []
        calls = []

        def fake_chat(model, messages, json_mode, timeout):
            calls.append((model, messages, json_mode, timeout))
            body = messages[-1]["content"]
            if "Schema requis" in body:
                return json.dumps(plan())
            target = "index.html" if '"path": "index.html"' in body else "style.css"
            content = "<!doctype html><html><body>ok</body></html>" if target == "index.html" else "body { color: black; }"
            return json.dumps({"kind": "write_file", "path": target, "language": target.split(".")[-1], "content": content})

        with tempfile.TemporaryDirectory() as directory:
            ok = run_agentic_stream(
                {"prompt": "cree une page", "model": "fake", "runId": 42},
                events.append,
                chat_client=fake_chat,
                output_root=Path(directory),
            )
            self.assertTrue(ok)
            self.assertEqual([event["kind"] for event in events].count("file.written"), 2)
            self.assertEqual(events[-1]["kind"], "done")
            self.assertEqual(events[-1]["finalScore"], 100)
            self.assertTrue((Path(directory) / "42/project/index.html").is_file())
            self.assertEqual(len(calls), 4)  # two plans, then two file actions


if __name__ == "__main__":
    unittest.main()
