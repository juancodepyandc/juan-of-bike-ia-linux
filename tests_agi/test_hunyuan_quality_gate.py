"""Verify delivery decisions independently of expensive model inference."""

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


@dataclass
class Scene:
    name: str = "fixture"
    prompt_image: str = "fixture"


class HunyuanQualityGateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.pipeline = types.ModuleType("pipeline_hunyuan_robust")
        self.pipeline.OUTPUT_ROOT = self.root
        for name in ("run_image_gen", "boost_and_rembg", "run_shape_gen", "run_tex_gen", "run_blender_animate"):
            setattr(self.pipeline, name, mock.Mock())
        classify = types.ModuleType("aurora_classify")
        classify.classify = mock.Mock(return_value=Scene())
        critic = types.ModuleType("aurora_critic")
        critic.evaluate = mock.Mock(return_value={"score": 0.8, "passed": True})
        source = Path(__file__).resolve().parents[1] / "application/python-services/aurora_hunyuan/aurora_loop_robust.py"
        spec = importlib.util.spec_from_file_location("quality_gate_fixture", source)
        self.module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"pipeline_hunyuan_robust": self.pipeline,
                                           "aurora_classify": classify, "aurora_critic": critic}):
            spec.loader.exec_module(self.module)
        self.pack = self.root / "pbr_fixture_pack"
        self.pack.mkdir()
        for filename in ("input_nobg.png", "shape_fixture.glb", "pbr_fixture_proc.glb"):
            (self.pack / filename).write_bytes(b"fixture")
        self.valid_audit = {"non_manifold_edges": 0, "degenerated_faces": 0,
                            "parts_count": 1, "total_faces": 100}
        self.real_audit = self.module.audit_shape
        patch = mock.patch.object(self.module, "audit_shape", return_value=self.valid_audit)
        self.audit = patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(self.module.subprocess, "run")
        self.commit = patch.start()
        self.addCleanup(patch.stop)

    def test_failed_or_missing_audit_never_reaches_texture_or_commit(self):
        for result in ({"error": "Blender crashed"}, {}, {**self.valid_audit, "total_faces": 0}):
            with self.subTest(result=result):
                self.audit.return_value = result
                self.assertFalse(self.module.process_scene("fixture", "fixture"))
                self.pipeline.run_blender_animate.assert_not_called()
                self.commit.assert_not_called()

    def test_failed_repair_keeps_original_and_does_not_publish(self):
        self.audit.return_value = {**self.valid_audit, "non_manifold_edges": 9}
        original = self.pack / "shape_fixture.glb"
        with mock.patch.object(self.module, "repair_shape", return_value=original):
            self.assertFalse(self.module.process_scene("fixture", "fixture"))
        self.assertEqual(original.read_bytes(), b"fixture")
        self.commit.assert_not_called()

    def test_repaired_geometry_is_validated_before_replacing_original(self):
        original = self.pack / "shape_fixture.glb"
        repaired = self.pack / "repaired.glb"
        repaired.write_bytes(b"still defective")
        self.audit.return_value = {**self.valid_audit, "degenerated_faces": 7}
        with mock.patch.object(self.module, "repair_shape", return_value=repaired):
            self.assertFalse(self.module.process_scene("fixture", "fixture"))
        self.assertEqual(original.read_bytes(), b"fixture")
        self.commit.assert_not_called()

    def test_rejected_unavailable_and_nonfinite_critics_never_commit(self):
        for critic in ({"score": 0.2, "passed": False}, {},
                       {"score": float("nan"), "passed": True},
                       {"score": 0.8, "passed": False}, {"score": 0.2, "passed": True}):
            with self.subTest(critic=critic):
                self.module.evaluate.return_value = critic
                self.assertFalse(self.module.process_scene("fixture", "fixture"))
                self.commit.assert_not_called()

    def test_accepted_geometry_and_critic_allow_commit(self):
        self.assertTrue(self.module.process_scene("fixture", "fixture"))
        self.assertEqual(self.commit.call_count, 2)

    def test_old_audit_is_discarded_when_blender_fails(self):
        old_audit = self.pack / "audit.json"
        old_audit.write_text('{"non_manifold_edges": 0}')
        self.commit.side_effect = subprocess.CalledProcessError(1, "blender")
        result = self.real_audit(self.pack / "shape_fixture.glb")
        self.assertIn("error", result)
        self.assertFalse(old_audit.exists())

    def test_valid_repair_invalidates_old_textured_mesh(self):
        original = self.pack / "shape_fixture.glb"
        repaired = self.pack / "repaired.glb"
        repaired.write_bytes(b"repaired")
        final = self.pack / "pbr_fixture_proc.glb"
        self.audit.side_effect = [{**self.valid_audit, "non_manifold_edges": 3}, self.valid_audit]

        def texture(shape, image, output, device):
            self.assertEqual(shape.read_bytes(), b"repaired")
            self.assertFalse(output.exists())
            output.write_bytes(b"textured repair")

        self.pipeline.run_tex_gen.side_effect = texture
        with mock.patch.object(self.module, "repair_shape", return_value=repaired):
            self.assertTrue(self.module.process_scene("fixture", "fixture"))
        self.pipeline.run_tex_gen.assert_called_once()
        self.assertEqual(original.read_bytes(), b"repaired")
        self.assertEqual(final.read_bytes(), b"textured repair")


if __name__ == "__main__":
    unittest.main()
