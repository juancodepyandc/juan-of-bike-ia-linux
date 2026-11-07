import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from auto_rl import colab_live_bridge as bridge


class ColabCandidateQuarantine(unittest.TestCase):
    def test_remote_loss_cannot_overwrite_existing_champion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "modele/renforce/code"
            module.mkdir(parents=True)
            champion = module / "adapter_colab_h100_full.safetensors"
            champion.write_bytes(b"existing model")
            manifest = module / "manifest.json"
            manifest.write_text('{"production":"preserve"}')
            with patch.object(bridge, "ROOT", root), patch.object(bridge, "COLAB_BRIDGE_STATE_FILE", root / "state.json"):
                result = bridge.receive_colab_trained_weights({"module": "code", "job_id": "native-candidate",
                    "weights_b64": base64.b64encode(b"unknown format bytes").decode(),
                    "metrics": {"final_loss": 0, "win_rate_pct": 100}})
                self.assertTrue(result["ok"])
                self.assertFalse(result["promoted"])
                self.assertEqual(champion.read_bytes(), b"existing model")
                self.assertEqual(manifest.read_text(), '{"production":"preserve"}')
                self.assertEqual(Path(result["saved_to"]).suffix, ".candidate")
                report = json.loads((module / "colab_h100_runs/native-candidate_report.json").read_text())
                self.assertFalse(report["promoted"])
                changed = bridge.receive_colab_trained_weights({"module": "code", "job_id": "native-candidate", "weights_b64": base64.b64encode(b"other bytes").decode()})
                self.assertFalse(changed["ok"])

    def test_job_paths_and_base64_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(bridge, "ROOT", Path(directory)):
            for job, data in (("../outside", "dGVzdA=="), ("valid", "not base64!")):
                result = bridge.receive_colab_trained_weights({"module": "code", "job_id": job, "weights_b64": data})
                self.assertFalse(result["ok"])

    def test_bootstrap_has_no_filler_allocations_and_reports_measured_ram(self):
        script = bridge.generate_colab_bootstrap_script("https://example.invalid")
        compile(script, "colab-bootstrap", "exec")
        self.assertNotIn("torch.empty((1024, 1024, 1024)", script)
        self.assertNotIn("target_bank_gb = 54.0", script)
        self.assertIn("psutil.Process().memory_info().rss", script)
