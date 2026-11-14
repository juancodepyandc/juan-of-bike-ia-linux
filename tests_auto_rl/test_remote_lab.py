import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from auto_rl import cloud_worker, remote_lab


class RemoteLab(unittest.TestCase):
    def test_notebook_cells_compile_without_embedded_trainer_or_implicit_training(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("Aurora_Verification_Kaggle.ipynb", "Aurora_Training_Colab.ipynb"):
            notebook = json.loads((root / "notebooks" / name).read_text())
            for cell in notebook["cells"]:
                if cell["cell_type"] == "code":
                    compile("".join(cell["source"]), name, "exec")
            if "Training" in name:
                self.assertIn("RUN_TRAINING = False", str(notebook))

    def test_native_worker_uses_explicit_paths_and_hash_verified_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "provided"
            inputs.mkdir()
            spec = {"job_id": "probe-run", "probe": True}
            payload = inputs / "payload.bin"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("spec.json", json.dumps(spec))
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
            torch = SimpleNamespace(__version__="fixture", cuda=SimpleNamespace(is_available=lambda: True, get_device_name=lambda _: "fixture"))
            with patch.dict("sys.modules", {"torch": torch}), contextlib.redirect_stdout(io.StringIO()):
                cloud_worker.main("probe-run", digest, work=root / "export", root=root / "unpacked", search_roots=[inputs])
            receipt = json.loads((root / "export/aurora_export/result.json").read_text())
            self.assertIsNone(receipt["error"])
            self.assertIn("probe.json", receipt["files"])
            self.assertTrue((root / "export/aurora_result.zip").is_file())

    def test_invalid_payload_cannot_start_native_worker(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(remote_lab, "probe_resources") as probe:
            with self.assertRaises(ValueError):
                remote_lab.run_payload(job_id="test", payload_hash="a" * 64,
                    inputs=Path(directory), output=Path(directory) / "outputs",
                    requirements={}, session_seconds=600)
            probe.assert_not_called()

    def test_validation_rejects_shell_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                remote_lab.validate_native(directory, suites=["tests_agi.test_x; rm"])
