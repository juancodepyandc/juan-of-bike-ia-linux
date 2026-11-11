"""Launcher and installation gates of the professor loop.

Ollama and Kaggle are SIMULATED here (recorded calls, temporary folders): these
tests prove the decision logic, not that a real kernel ran or a real model was
installed. Real runs are recorded as dated observations in the master document.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_rl.professor import install, kaggle_runner
from auto_rl.professor.records import atomic_json, file_hash


class Launcher(unittest.TestCase):
    def test_script_is_self_contained_and_holds_no_credential(self):
        options = {"role": "diagnose", "student": "qwen2.5:7b", "profile": "standard", "modules": "business",
                   "cycle": 0, "budget_minutes": 30, "overrides": {}}
        text = kaggle_runner.script(options)
        compile(text, "kernel.py", "exec")
        compile(kaggle_runner.script(), "notebook-cell.py", "exec")
        blob, digest, manifest = kaggle_runner.bundle()
        self.assertIn(digest, text)
        self.assertTrue(all(name.endswith((".py", ".json")) for name in manifest))
        self.assertIn("auto_rl/professor/run.py", manifest)
        self.assertIn("agi_core/json_evidence.py", manifest)      # production oracle travels with the exam
        for forbidden in ("KGAT_", "KAGGLE_KEY=", "hf_", "Authorization"):
            self.assertNotIn(forbidden, text.replace("HF_TOKEN", ""))

    def test_each_student_has_its_own_private_examiner_and_trainer(self):
        with tempfile.TemporaryDirectory() as folder:
            diagnose = kaggle_runner.write_kernel(Path(folder) / "d", "owner", "diagnose", student="qwen2.5:7b")
            train = kaggle_runner.write_kernel(Path(folder) / "t", "owner", "train", student="qwen2.5:7b")
            verify = kaggle_runner.write_kernel(Path(folder) / "v", "owner", "verify", student="qwen2.5:7b", cycle=2)
            colab = kaggle_runner.write_kernel(Path(folder) / "c", "owner", "verify", student="qwen2.5:7b",
                                               dataset_sources=["owner/aurora-professeur-adaptateurs"])
            other = kaggle_runner.write_kernel(Path(folder) / "o", "owner", "diagnose", student="qwen2.5-coder:7b")
            launch = json.loads((Path(folder) / "v" / "launch.json").read_text())
        for metadata in (diagnose, train, verify, colab, other):
            self.assertIs(metadata["is_private"], True)
            self.assertIs(metadata["enable_gpu"], True)
        self.assertEqual(diagnose["id"], verify["id"])                       # one examiner machine per student
        self.assertNotEqual(diagnose["id"], train["id"])                     # never the trainer's machine
        self.assertNotEqual(diagnose["id"], other["id"])
        self.assertEqual(diagnose["kernel_sources"], [])
        self.assertEqual(train["kernel_sources"], [diagnose["id"]])          # the trainer reads the diagnosis only
        self.assertEqual(verify["kernel_sources"], [train["id"]])            # the examiner reads the adapter only
        self.assertEqual(colab["kernel_sources"], [])
        self.assertEqual(colab["dataset_sources"], ["owner/aurora-professeur-adaptateurs"])
        self.assertEqual(launch["options"]["cycle"], 2)
        self.assertEqual(launch["sources_sha256"], kaggle_runner.bundle()[1])

    def test_fetch_refuses_output_that_differs_from_the_remote_manifest(self):
        class Api:
            def kernels_output(self, reference, path, force, quiet):
                work = Path(path) / "aurora_professor"
                work.mkdir(parents=True)
                (work / "diagnosis.json").write_text("{}")
                manifest = {"exit_code": 0, "files": {"diagnosis.json": "0" * 64}}
                (Path(path) / "aurora_professor_manifest.json").write_text(json.dumps(manifest))
        with tempfile.TemporaryDirectory() as folder, patch.object(kaggle_runner, "_api", return_value=Api()):
            with self.assertRaises(RuntimeError):
                kaggle_runner.fetch("owner/kernel", folder)


class Installation(unittest.TestCase):
    def delivery(self, folder, *, verdict="promote", student="qwen2.5:7b", promotable=True, tamper=None):
        folder = Path(folder)
        adapter = folder / "aurora_professor" / "training" / "adapter"
        adapter.mkdir(parents=True)
        (adapter / "adapter_config.json").write_text("{}")
        (adapter / "adapter_model.safetensors").write_bytes(b"adapter-weights")
        export = folder / "aurora_professor" / "export"
        export.mkdir()
        (export / "adapter.gguf").write_bytes(b"gguf-adapter")
        sha = file_hash(adapter / "adapter_model.safetensors")
        atomic_json(export / "export_receipt.json", {"adapter_sha256": sha, "files": {
            "adapter.gguf": {"sha256": file_hash(export / "adapter.gguf"), "bytes": 12}}})
        atomic_json(folder / "aurora_professor" / "verdict_0.json", {
            "kind": "aurora_professor_verdict", "verdict": verdict, "promotable": promotable, "exam_complete": True,
            "student": {"tag": student}, "adapter_sha256": sha, "cycle": 0, "modules": ["business"],
            "overall": {"macro_gain": 0.11, "macro_gain_ci": [0.05, 0.17]}})
        if tamper == "adapter":
            (adapter / "adapter_model.safetensors").write_bytes(b"another adapter")
        if tamper == "gguf":
            (export / "adapter.gguf").write_bytes(b"altered")
        return folder

    def test_only_a_matching_promoted_production_delivery_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(install.check_delivery(self.delivery(folder))["problems"], [])
        for changes in ({"verdict": "inconclusive", "promotable": False}, {"verdict": "reject", "promotable": False},
                        {"promotable": False}, {"student": "qwen3:0.6b"}, {"tamper": "adapter"}, {"tamper": "gguf"}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as folder:
                self.assertTrue(install.check_delivery(self.delivery(folder, **changes))["problems"])
                with patch.object(install, "ollama") as command, patch.object(install, "installed_tags", return_value={}):
                    with self.assertRaises(ValueError):
                        install.install(folder)
                    command.assert_not_called()                 # nothing reaches Ollama for a refused delivery

    def simulated(self, state, deployment_verdict):
        """A stand-in for Ollama: tags are a dict, commands are recorded."""
        tags, calls = {"qwen2.5:7b": "base-digest"}, []

        def command(*arguments, **_):
            calls.append(arguments)
            if arguments[0] == "create":
                tags[arguments[1]] = "candidate-digest"
            if arguments[0] == "cp":
                tags[arguments[2]] = tags[arguments[1]]
            return ""
        exam = {"verdict": deployment_verdict, "reasons": ["simulated"], "regressions": [],
                "overall": {"macro_gain": 0.1, "macro_gain_ci": [0.02, 0.2], "items": 240}}
        return tags, calls, [patch.object(install, "ollama", side_effect=command),
                             patch.object(install, "installed_tags", side_effect=lambda url: dict(tags)),
                             patch.object(install, "deployment_exam", return_value=exam),
                             patch.object(install, "STATE", Path(state))]

    def test_simulated_ollama_activation_needs_a_win_as_served_and_is_reversible(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as state:
            tags, calls, patches = self.simulated(state, "promote")
            for item in patches:
                item.start()
            try:
                record = install.install(self.delivery(folder))
                self.assertEqual(record["candidate_tag"], "qwen2.5:7b-aurora-renforce-c0")
                self.assertFalse(record["active"])
                self.assertEqual(tags["qwen2.5:7b"], "base-digest")                  # installing changes no default
                active = install.activate("qwen2.5:7b")
                self.assertTrue(active["active"])
                self.assertEqual(tags["qwen2.5:7b"], "candidate-digest")             # the application's tag is reinforced
                self.assertEqual(tags["qwen2.5:7b-aurora-base"], "base-digest")      # original weights preserved
                self.assertEqual(active["rollback"], "ollama cp qwen2.5:7b-aurora-base qwen2.5:7b")
                install.activate("qwen2.5:7b")                                       # activating twice keeps the backup intact
                self.assertEqual(tags["qwen2.5:7b-aurora-base"], "base-digest")
                install.rollback("qwen2.5:7b")
                self.assertEqual(tags["qwen2.5:7b"], "base-digest")
                self.assertFalse(json.loads((Path(state) / "installed.json").read_text())["qwen2.5:7b"]["active"])
            finally:
                for item in patches:
                    item.stop()
        self.assertEqual(calls[0][0], "create")

    def test_simulated_ollama_refuses_activation_without_a_deployment_win(self):
        for verdict in ("inconclusive", "reject"):
            with self.subTest(verdict=verdict), tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as state:
                tags, calls, patches = self.simulated(state, verdict)
                for item in patches:
                    item.start()
                try:
                    install.install(self.delivery(folder))
                    with self.assertRaises(ValueError):
                        install.activate("qwen2.5:7b")
                    self.assertEqual(tags["qwen2.5:7b"], "base-digest")
                    self.assertNotIn("qwen2.5:7b-aurora-base", tags)
                finally:
                    for item in patches:
                        item.stop()

    def test_simulated_ollama_refuses_a_model_changed_after_its_exam(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as state:
            tags, calls, patches = self.simulated(state, "promote")
            for item in patches:
                item.start()
            try:
                install.install(self.delivery(folder))
                tags["qwen2.5:7b-aurora-renforce-c0"] = "someone-else-rebuilt-it"
                with self.assertRaises(ValueError):
                    install.activate("qwen2.5:7b")
                self.assertEqual(tags["qwen2.5:7b"], "base-digest")
            finally:
                for item in patches:
                    item.stop()


class OllamaBackend(unittest.TestCase):
    """Real HTTP exchanges with a stand-in server speaking the Ollama chat API."""

    def serve(self, handler):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *arguments):
                pass

            def do_GET(self):
                self._send(200, {"models": [{"name": "demo:1", "digest": "abc"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                status, payload = handler(body)
                self._send(status, payload)

            def _send(self, status, payload):
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_requests_are_deterministic_and_a_missing_reasoning_mode_is_handled(self):
        from auto_rl.professor.inference import OllamaStudent
        seen = []

        def handler(body):
            seen.append(body)
            if "think" in body:
                return 400, {"error": "\"demo:1\" does not support thinking"}
            return 200, {"message": {"content": "B"}, "done_reason": "stop"}
        student = OllamaStudent("demo:1", url=self.serve(handler), context=4096)
        answers = student.generate([[{"role": "user", "content": "q1"}], [{"role": "user", "content": "q2"}]], 8)
        self.assertEqual(answers, ["B", "B"])
        self.assertEqual(len(seen), 3)                      # one refusal, then two plain requests
        self.assertEqual(seen[-1]["options"], {"temperature": 0, "seed": 0, "num_predict": 8, "num_ctx": 4096})
        self.assertIs(seen[-1]["stream"], False)
        self.assertEqual(student.describe()["digest"], "abc")

    def test_a_spent_budget_without_answer_is_an_empty_answer_and_errors_are_not_scores(self):
        from auto_rl.professor.inference import OllamaStudent
        url = self.serve(lambda body: (200, {"message": {"content": ""}, "done_reason": "length"}))
        self.assertEqual(OllamaStudent("demo:1", url=url).generate([[{"role": "user", "content": "q"}]], 4), [""])
        broken = self.serve(lambda body: (500, {"error": "model failed to load"}))
        with self.assertRaises(RuntimeError):
            OllamaStudent("demo:1", url=broken).generate([[{"role": "user", "content": "q"}]], 4)


if __name__ == "__main__":
    unittest.main()
