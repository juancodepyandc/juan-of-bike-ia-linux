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
            verify = kaggle_runner.write_kernel(Path(folder) / "v0", "owner", "verify", student="qwen2.5:7b")
            kaggle_runner.write_kernel(Path(folder) / "v", "owner", "verify", student="qwen2.5:7b", cycle=2)
            colab = kaggle_runner.write_kernel(Path(folder) / "c", "owner", "verify", student="qwen2.5:7b",
                                               dataset_sources=["owner/aurora-professeur-adaptateurs"])
            other = kaggle_runner.write_kernel(Path(folder) / "o", "owner", "diagnose", student="qwen2.5-coder:7b")
            launch = json.loads((Path(folder) / "v" / "launch.json").read_text())
        for metadata in (diagnose, train, verify, colab, other):
            self.assertIs(metadata["is_private"], True)
            self.assertIs(metadata["enable_gpu"], True)
        self.assertEqual(diagnose["id"], verify["id"])                       # one examiner machine per student and cycle
        self.assertNotEqual(diagnose["id"], train["id"])                     # never the trainer's machine
        self.assertNotEqual(diagnose["id"], other["id"])
        self.assertEqual(diagnose["kernel_sources"], [])
        self.assertEqual(train["kernel_sources"], [diagnose["id"]])          # the trainer reads the diagnosis only
        self.assertEqual(verify["kernel_sources"], [train["id"]])            # the examiner reads the adapter only
        self.assertEqual(colab["kernel_sources"], [])
        self.assertEqual(colab["dataset_sources"], ["owner/aurora-professeur-adaptateurs"])
        self.assertEqual(launch["options"]["cycle"], 2)
        self.assertEqual(launch["sources_sha256"], kaggle_runner.bundle()[1])

    def test_the_extracted_sources_can_publish_and_relaunch_with_the_same_bundle(self):
        """The Colab trainer imports the launcher from the extracted bundle; found missing on 2026-11-12."""
        import subprocess
        import sys
        from auto_rl.source_bundle import extract_bundle
        blob, digest, manifest = kaggle_runner.bundle()
        self.assertIn("auto_rl/professor/kaggle_runner.py", manifest)
        with tempfile.TemporaryDirectory() as folder:
            repo = extract_bundle(blob, Path(folder) / "sources", digest)
            code = ("import sys; sys.path.insert(0, sys.argv[1]); from auto_rl.professor import kaggle_runner as k; "
                    "import tempfile, pathlib; d = pathlib.Path(tempfile.mkdtemp()); "
                    "k.write_kernel(d, 'owner', 'verify', student='qwen2.5:7b', dataset_sources=['owner/x']); "
                    "assert k.ROOT == pathlib.Path(sys.argv[1]).resolve(), k.ROOT; print(k.bundle()[1])")
            done = subprocess.run([sys.executable, "-I", "-c", code, str(repo)], capture_output=True, text=True, cwd=folder)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        self.assertEqual(done.stdout.strip(), digest)

    def run_bootstrap(self, folder, options, files):
        """Execute the generated kernel with the role process replaced by a recorder; returns its argv."""
        folder = Path(folder)
        for name in files:
            target = folder / "input" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}")
        text = kaggle_runner.script(options, base=str(folder / "working"), inputs=str(folder / "input"),
                                    hf_home=str(folder / "hf"), sources=str(folder / "sources"))
        calls = []

        class Process:
            stdout = ()

            def __init__(self, argv, **_):
                calls.append(argv)

            def wait(self):
                return 0
        with patch("subprocess.Popen", Process), patch("subprocess.run"), patch("builtins.print"):
            exec(compile(text, "kernel.py", "exec"), {"__name__": "__kernel__"})
        return calls[0]

    def test_a_continued_cycle_passes_the_candidate_diagnosis_and_both_adapters(self):
        base = {"student": "qwen2.5:7b", "profile": "standard", "modules": "business", "budget_minutes": 30, "overrides": {}}
        with tempfile.TemporaryDirectory() as folder:
            # Trainer of cycle 1 mounted on the examiner's last output: candidate adapter plus its diagnosis.
            argv = self.run_bootstrap(Path(folder) / "t", {**base, "role": "train", "cycle": 1, "continue": True},
                                      ["examiner/aurora_professor/diagnosis_next_0.json",
                                       "examiner/aurora_professor/training/adapter/adapter_config.json",
                                       "examiner/aurora_professor/training/init_adapter/adapter_config.json"])
            self.assertTrue(argv[argv.index("--diagnosis") + 1].endswith("diagnosis_next_0.json"))
            self.assertTrue(argv[argv.index("--init-adapter") + 1].endswith("training/adapter"))
            # Examiner of cycle 1: the new adapter is the candidate, the one it continues sits the same exam.
            argv = self.run_bootstrap(Path(folder) / "v", {**base, "role": "verify", "cycle": 1},
                                      ["trainer/aurora_professor/training/adapter/adapter_config.json",
                                       "trainer/aurora_professor/training/init_adapter/adapter_config.json"])
            self.assertTrue(argv[argv.index("--adapter") + 1].endswith("working/aurora_professor/training/adapter"))
            self.assertTrue(argv[argv.index("--previous-adapter") + 1].endswith("working/aurora_professor/training/init_adapter"))
            # Colab path: a flat private dataset carries the continued adapter under an ``init_`` prefix.
            argv = self.run_bootstrap(Path(folder) / "c", {**base, "role": "verify", "cycle": 1},
                                      ["dataset/adapter_config.json", "dataset/adapter_model.safetensors",
                                       "dataset/init_adapter_config.json", "dataset/init_adapter_model.safetensors"])
            before = Path(argv[argv.index("--previous-adapter") + 1])
            self.assertEqual(sorted(p.name for p in before.iterdir()), ["adapter_config.json", "adapter_model.safetensors"])
            # A first cycle is unchanged: one diagnosis, no starting adapter, no previous adapter.
            argv = self.run_bootstrap(Path(folder) / "f", {**base, "role": "train", "cycle": 0}, ["examiner/diagnosis.json"])
            self.assertNotIn("--init-adapter", argv)
            argv = self.run_bootstrap(Path(folder) / "g", {**base, "role": "verify", "cycle": 0}, ["trainer/training/adapter/adapter_config.json"])
            self.assertNotIn("--previous-adapter", argv)
            with self.assertRaises(SystemExit):          # a continuation without the candidate's diagnosis is refused
                self.run_bootstrap(Path(folder) / "x", {**base, "role": "train", "cycle": 1, "continue": True},
                                   ["examiner/diagnosis.json", "examiner/training/adapter/adapter_config.json"])
            continued = kaggle_runner.write_kernel(Path(folder) / "k", "owner", "train", student="qwen2.5:7b", cycle=1,
                                                   continue_adapter=True, dataset_sources=["owner/aurora-professeur-adaptateurs-qwen25-7b"])
            self.assertEqual(continued["kernel_sources"], [])      # one source of truth for the starting adapter
            self.assertIs(json.loads((Path(folder) / "k" / "launch.json").read_text())["options"]["continue"], True)
            # A later cycle that trains a new adapter from the base carries the base diagnosis itself.
            (Path(folder) / "base_diagnosis.json").write_text('{"kind": "aurora_professor_diagnosis", "n": 1}')
            fresh = kaggle_runner.write_kernel(Path(folder) / "n", "owner", "train", student="qwen2.5:7b", cycle=1,
                                               diagnosis=Path(folder) / "base_diagnosis.json")
            self.assertEqual((fresh["kernel_sources"], fresh["dataset_sources"]), ([], []))
            self.assertNotIn("diagnosis_b64", json.loads((Path(folder) / "n" / "launch.json").read_text())["options"])
            text = (Path(folder) / "n" / "kernel.py").read_text()
            options = json.loads(eval(text[text.index("OPTIONS = json.loads(") + len("OPTIONS = json.loads("):text.index(")\nSOURCE_SHA256")]))
            argv = self.run_bootstrap(Path(folder) / "nb", options, [])
            self.assertEqual(json.loads(Path(argv[argv.index("--diagnosis") + 1]).read_text())["n"], 1)
            self.assertNotIn("--init-adapter", argv)
            # Each cycle has its own pair of kernels, so an earlier verdict and its files stay downloadable.
            first = kaggle_runner.write_kernel(Path(folder) / "v0", "owner", "verify", student="qwen2.5:7b")
            later_train = kaggle_runner.write_kernel(Path(folder) / "t1", "owner", "train", student="qwen2.5:7b", cycle=1, continue_adapter=True)
            later_verify = kaggle_runner.write_kernel(Path(folder) / "v1", "owner", "verify", student="qwen2.5:7b", cycle=1)
            self.assertEqual(later_train["kernel_sources"], [first["id"]])            # previous examiner: verdict's diagnosis + adapter
            self.assertEqual(later_verify["kernel_sources"], [later_train["id"]])
            self.assertEqual(len({first["id"], later_train["id"], later_verify["id"]}), 3)
            self.assertTrue(later_verify["id"].endswith("-c1"))
            with self.assertRaises(ValueError):
                kaggle_runner.write_kernel(Path(folder) / "z", "owner", "train", student="qwen2.5:7b", continue_adapter=True)

    def test_each_student_publishes_to_its_own_private_dataset(self):
        seen = []

        class Api:
            def dataset_status(self, reference):
                raise RuntimeError("absent")

            def dataset_create_new(self, folder, public, quiet):
                seen.append((json.loads((Path(folder) / "dataset-metadata.json").read_text())["id"], public,
                             sorted(p.name for p in Path(folder).iterdir())))
        with tempfile.TemporaryDirectory() as folder, patch.object(kaggle_runner, "_api", return_value=Api()):
            adapter = Path(folder) / "training" / "adapter"
            adapter.mkdir(parents=True)
            (adapter / "adapter_config.json").write_text("{}")
            (adapter / "adapter_model.safetensors").write_bytes(b"w")
            (Path(folder) / "diagnosis_next_0.json").write_text("{}")
            before = Path(folder) / "training" / "init_adapter"
            before.mkdir()
            (before / "adapter_config.json").write_text("{}")
            (before / "adapter_model.safetensors").write_bytes(b"v")
            first = kaggle_runner.publish_adapter("owner", Path(folder) / "training", student="qwen2.5:7b",
                                                  extra=[Path(folder) / "diagnosis_next_0.json"])
            second = kaggle_runner.publish_adapter("owner", Path(folder) / "training", student="qwen2.5-coder:7b")
        self.assertNotEqual(first, second)
        self.assertEqual(first, "owner/aurora-professeur-adaptateurs-qwen25-7b")
        self.assertTrue(all(public is False for _, public, _ in seen))
        self.assertIn("diagnosis_next_0.json", seen[0][2])
        self.assertIn("init_adapter_model.safetensors", seen[0][2])

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

    def test_a_continued_delivery_ships_the_new_adapter_unless_it_is_worse_than_the_one_it_continues(self):
        with tempfile.TemporaryDirectory() as folder:
            delivery = self.delivery(folder)
            before = delivery / "aurora_professor" / "training" / "init_adapter"
            before.mkdir()
            (before / "adapter_model.safetensors").write_bytes(b"previous-weights")
            self.assertEqual(install.check_delivery(delivery)["problems"], [])       # the starting adapter is not the delivery
            path = delivery / "aurora_professor" / "verdict_0.json"
            verdict = json.loads(path.read_text())
            atomic_json(path, {**verdict, "versus_previous": {"verdict": "inconclusive"}})
            self.assertEqual(install.check_delivery(delivery)["problems"], [])
            atomic_json(path, {**verdict, "versus_previous": {"verdict": "reject"}})
            self.assertTrue(any("cycle précédent" in problem for problem in install.check_delivery(delivery)["problems"]))

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
