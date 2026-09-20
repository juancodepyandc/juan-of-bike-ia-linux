"""A simulated image must never certify real inference or visual correctness."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image


class ImageBenchmarkContractTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[1] / "application/python-services"
        spec = importlib.util.spec_from_file_location("image_benchmark_fixture", directory / "run_deep_image_benchmark.py")
        self.module = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "path", [str(directory), *sys.path]):
            spec.loader.exec_module(self.module)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        Image.new("RGB", (16, 16)).save(self.root / "image.png")
        (self.root / "metadata.json").write_text("{}")
        self.manifest = {
            "category": "fixture", "main_category": "assets",
            "package_files": {"master_image": str(self.root / "image.png"),
                              "metadata_file": str(self.root / "metadata.json")},
            "quality_assurance_metrics": {"status": "SIMULATED_NOT_EVALUATED", "dominant_palette_hex": ["#000000"]},
            "generation_params": {"engine": "simulation"},
            "dimensions": {"width": 16, "height": 16},
        }
        self.case = {"prompt": "fixture", "expected_category": "fixture", "expected_dir": "assets"}

    def test_simulation_is_rejected_as_real_inference(self):
        with self.assertRaisesRegex(ValueError, "measurement status"):
            self.module.validate_manifest(self.manifest, self.case, simulate=False)
        self.manifest["quality_assurance_metrics"]["status"] = "MEASURED_NOT_EVALUATED"
        with self.assertRaisesRegex(ValueError, "mode do not match"):
            self.module.validate_manifest(self.manifest, self.case, simulate=False)

    def test_actual_dimensions_are_checked(self):
        self.manifest["dimensions"]["width"] = 1024
        with self.assertRaisesRegex(ValueError, "dimensions differ"):
            self.module.validate_manifest(self.manifest, self.case, simulate=True)

    def test_corrupted_image_cannot_validate_a_package(self):
        (self.root / "image.png").write_bytes(b"invalid PNG")
        with self.assertRaises(OSError):
            self.module.validate_manifest(self.manifest, self.case, simulate=True)

    def test_failed_real_job_is_recorded_without_fallback_or_quality_claim(self):
        with mock.patch.object(self.module, "BENCHMARK_PROMPTS", [self.case]), mock.patch.object(
            self.module, "generate_image_manifest", side_effect=RuntimeError("ComfyUI unavailable")
        ) as generate:
            result = self.module.run_benchmark(self.root, seed=17)
        self.assertEqual(result["valid_packages"], 0)
        self.assertEqual(result["cases"][0]["status"], "FAILED")
        self.assertEqual(result["semantic_evaluation"], "NOT_EVALUATED")
        self.assertEqual(result["mode"], "REAL_INFERENCE")
        self.assertTrue(generate.call_args.kwargs["use_comfy"])
        self.assertEqual(generate.call_args.kwargs["seed"], 17)
        self.assertEqual(json.loads((self.root / "benchmark.json").read_text())["valid_packages"], 0)


if __name__ == "__main__":
    unittest.main()
