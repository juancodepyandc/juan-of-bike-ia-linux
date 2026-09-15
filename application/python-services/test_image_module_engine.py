#!/usr/bin/env python3
"""Unit tests for AuroraIA Subject-Oriented Image Module Engine."""

import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from PIL import Image
import sys

sys.path.append(str(Path(__file__).parent))
from human_prompt_director import detect_category, direct_prompt
from image_module_engine import generate_image_manifest

class TestImageSubjectModule(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output_dir = Path(temporary.name)

    def test_portrait_subject_bundle(self):
        m = generate_image_manifest(
            "photo portrait 85mm d un astronaute",
            output_dir=self.output_dir / "astronaute_portrait",
            use_comfy=False
        )
        self.assertEqual(m["category"], "photo_realistic")
        d = Path(m["package_files"]["directory"])
        self.assertTrue((d / "image.png").exists())
        self.assertTrue((d / "prompt.txt").exists())
        self.assertTrue((d / "metadata.json").exists())
        self.assertTrue((d / "palette.json").exists())
        self.assertTrue((d / "README.md").exists())
        self.assertTrue((d / "avatar_crop_512x512.png").exists())
        self.assertTrue((d / "detail_macro_crop.png").exists())

    def test_game_asset_icon_subject_bundle(self):
        m = generate_image_manifest(
            "potion magique de soin rouge brillante pour icone rpg",
            output_dir=self.output_dir / "potion_soin_rpg",
            use_comfy=False
        )
        self.assertEqual(m["category"], "game_asset_icon_ui")
        d = Path(m["package_files"]["directory"])
        self.assertTrue((d / "image.png").exists())
        self.assertTrue((d / "asset_isolated_alpha.png").exists())
        self.assertTrue((d / "icon_512x512.png").exists())
        self.assertTrue((d / "icon_64x64.png").exists())

    def test_texture_seamless_subject_bundle(self):
        m = generate_image_manifest(
            "texture sol pave de donjon seamless tileable",
            output_dir=self.output_dir / "texture_donjon_pave",
            use_comfy=False
        )
        self.assertEqual(m["category"], "game_asset_texture")
        d = Path(m["package_files"]["directory"])
        self.assertTrue((d / "seamless_2x2_tiling.png").exists())
        self.assertTrue((d / "normal_map_simulated.png").exists())
        self.assertTrue((d / "height_map.png").exists())

    def test_live_generation_failure_does_not_publish_a_simulated_package(self):
        target = self.output_dir / "offline"
        with patch("image_module_engine.urllib.request.urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(RuntimeError, "ComfyUI"):
                generate_image_manifest("photo portrait", output_dir=target)
        self.assertFalse((target / "image.png").exists())
        self.assertFalse((target / "metadata.json").exists())

    def test_explicit_simulation_is_labelled_and_preserves_seed_zero(self):
        manifest = generate_image_manifest("photo portrait", output_dir=self.output_dir, seed=0, use_comfy=False)
        self.assertEqual(manifest["generation_params"]["seed"], 0)
        self.assertEqual(manifest["generation_params"]["engine"], "simulation")
        self.assertEqual(manifest["quality_assurance_metrics"]["status"], "SIMULATED_NOT_EVALUATED")

    def test_empty_live_job_preserves_existing_package_files(self):
        existing = self.output_dir / "image.png"
        existing.write_bytes(b"existing render")
        with patch("image_module_engine.urllib.request.urlopen") as urlopen, \
             patch("image_module_engine.submit_comfy_prompt", return_value="test-job"), \
             patch("image_module_engine.wait_for_comfy_image", return_value=None):
            urlopen.return_value.__enter__.return_value.status = 200
            with self.assertRaisesRegex(RuntimeError, "ComfyUI produced no image"):
                generate_image_manifest("photo portrait", output_dir=self.output_dir)
        self.assertEqual(existing.read_bytes(), b"existing render")
        self.assertFalse((self.output_dir / "metadata.json").exists())

    def test_live_image_reports_measurements_without_claiming_a_quality_pass(self):
        import io
        image = io.BytesIO()
        Image.new("RGB", (32, 32), "blue").save(image, format="PNG")
        with patch("image_module_engine.urllib.request.urlopen") as urlopen, \
             patch("image_module_engine.submit_comfy_prompt", return_value="test-job"), \
             patch("image_module_engine.wait_for_comfy_image", return_value=image.getvalue()):
            urlopen.return_value.__enter__.return_value.status = 200
            manifest = generate_image_manifest("photo portrait", output_dir=self.output_dir)
        self.assertEqual(manifest["generation_params"]["engine"], "flux2_dev_comfyui_cuda")
        self.assertEqual(manifest["quality_assurance_metrics"]["status"], "MEASURED_NOT_EVALUATED")

if __name__ == "__main__":
    unittest.main()
