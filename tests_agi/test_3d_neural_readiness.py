"""3D routing/readiness regression tests; no models, GPU or external requests."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "application" / "python-services"


def module(name, **attrs):
    result = types.ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load_source(name, path, dependencies):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, dependencies), patch.object(sys, "path", list(sys.path)):
        spec.loader.exec_module(result)
    return result


def pipeline_module():
    dependencies = {
        "subject_kind_extractor": module("subject_kind_extractor", extract_kind=Mock(return_value={
            "kind": "sphere", "confidence": 1, "matched_pattern": "sphere"})),
        "flux_reference_synth": module("flux_reference_synth", synth=Mock(),
            synth_multiview=Mock(), audit_multiview_consistency=Mock()),
        "auto_rescue_mesh": module("auto_rescue_mesh", auto_rescue=Mock()),
        "neural_process": module("neural_process", run_neural_process=Mock()),
        "faithful_scene_prompt": module("faithful_scene_prompt",
            compose_faithful_prompt=None, refine_subject_kind=None),
        "optimize_textured_mesh": module("optimize_textured_mesh", optimize=None),
        "tracker_helper": module("tracker_helper", record_dispatch=None),
        "route_test": module("route_test", route_pipeline=None),
    }
    return load_source("test_pipeline_readiness", SERVICES / "aurora_3d_pipeline.py", dependencies)


class TrellisReadinessTests(unittest.TestCase):
    def setUp(self):
        self.cuda = Mock()
        self.cuda.is_available.return_value = True
        self.torch = module("torch", cuda=self.cuda)
        self.wrapper = load_source("test_trellis_readiness",
            SERVICES / "aurora_hunyuan" / "aurora_trellis_wrapper.py", {
                "torch": self.torch,
                "flex_gemm": module("flex_gemm"), "cumesh": module("cumesh"),
                "o_voxel": module("o_voxel"),
                "nvdiffrast": module("nvdiffrast", __path__=[]),
                "nvdiffrast.torch": module("nvdiffrast.torch"),
                "trellis2": module("trellis2", __path__=[]),
                "trellis2.pipelines": module("trellis2.pipelines", Trellis2ImageTo3DPipeline=Mock()),
            })

    def test_successful_imports_without_cuda_are_unavailable(self):
        self.assertTrue(self.wrapper._AVAILABLE)
        self.cuda.is_available.return_value = False
        self.assertFalse(self.wrapper.is_available())
        self.assertIn("CUDA indisponible", self.wrapper.import_error())
        self.cuda.init.assert_not_called()

    def test_cuda_initialisation_failure_is_reported(self):
        self.cuda.init.side_effect = RuntimeError("driver unavailable for running kernel")
        self.assertFalse(self.wrapper.is_available())
        self.assertIn("driver unavailable for running kernel", self.wrapper.import_error())

    def test_generation_is_rejected_before_loading_weights(self):
        self.cuda.is_available.return_value = False
        with patch.object(self.wrapper, "_load_pipe") as loader:
            result = self.wrapper.generate_glb("input.png", "out.glb")
        self.assertFalse(result["ok"])
        self.assertIn("CUDA indisponible", result["error"])
        loader.assert_not_called()

    def test_healthy_cuda_and_imports_preserve_boolean_api(self):
        self.assertIs(self.wrapper.is_available(), True)
        self.assertIsNone(self.wrapper.import_error())


class EngineProbeTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = pipeline_module()
        self.cuda = Mock()
        self.cuda.is_available.return_value = True
        self.wrapper = module("aurora_trellis_wrapper", is_available=Mock(return_value=True),
                              import_error=Mock(return_value=None))

    def execute_probe(self, argv, **kwargs):
        output = io.StringIO()
        with patch.dict(sys.modules, {"torch": module("torch", cuda=self.cuda),
                                      "aurora_trellis_wrapper": self.wrapper}), \
                patch.object(sys, "argv", ["-c", *argv[3:]]), \
                patch.object(sys, "path", list(sys.path)), contextlib.redirect_stdout(output):
            exec(argv[2], {"__name__": "__main__"})
        return subprocess.CompletedProcess(argv, 0, output.getvalue(), "")

    def test_probe_uses_execution_interpreter_and_cuda(self):
        with patch.object(self.pipeline, "trellis_python", return_value="/engine/python"), \
                patch.object(self.pipeline.subprocess, "run", side_effect=self.execute_probe) as runner:
            result = self.pipeline.neural_engine_readiness("trellis")
        self.assertTrue(result["available"])
        self.assertEqual(runner.call_args.args[0][0], "/engine/python")
        self.cuda.init.assert_called_once()

    def test_missing_cuda_short_circuits_engine_imports(self):
        self.cuda.is_available.return_value = False
        with patch.object(self.pipeline.subprocess, "run", side_effect=self.execute_probe):
            result = self.pipeline.neural_engine_readiness("trellis")
        self.assertFalse(result["available"])
        self.assertIn("CUDA indisponible", result["error"])
        self.wrapper.is_available.assert_not_called()

    def test_cuda_initialisation_error_short_circuits_engine(self):
        self.cuda.init.side_effect = RuntimeError("CUDA driver initialization failed")
        with patch.object(self.pipeline.subprocess, "run", side_effect=self.execute_probe):
            result = self.pipeline.neural_engine_readiness("trellis")
        self.assertFalse(result["available"])
        self.assertIn("CUDA driver initialization failed", result["error"])
        self.wrapper.is_available.assert_not_called()

    def test_probe_timeout_reports_failure(self):
        with patch.object(self.pipeline.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 60)):
            result = self.pipeline.neural_engine_readiness("hunyuan3d")
        self.assertFalse(result["available"])
        self.assertIn("60 secondes", result["error"])

    def test_expired_readiness_cache_rechecks_driver(self):
        with patch.object(self.pipeline.subprocess, "run", side_effect=self.execute_probe) as runner, \
                patch.object(self.pipeline.time, "monotonic", side_effect=[0, 1, 20, 20]):
            self.pipeline.neural_engine_readiness("trellis")
            self.pipeline.neural_engine_readiness("trellis")
            self.pipeline.neural_engine_readiness("trellis")
        self.assertEqual(runner.call_count, 2)


class PipelinePreflightTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = pipeline_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_dir = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"AURORA_LOG_DISQUE": "0", "AURORA_SCENE_ORCH": "0",
            "AURORA_MESHY": "0", "AURORA_3D_ENGINE": "auto", "AURORA_RECTIFIER": "0",
            "AURORA_REFERENCE_RESEARCH": "0", "AURORA_REF_CONFIRM": "0"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch.object(self.pipeline.urllib.request, "urlopen", side_effect=OSError("offline test"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.pipeline.trellis_is_available = Mock(return_value=False)
        self.pipeline.neural_engine_readiness = Mock(side_effect=lambda engine: {
            "available": False, "engine": engine, "python": "/engine/python", "error": "CUDA indisponible"})
        self.pipeline._record_pipeline_dispatch = Mock()
        self.pipeline.run_procedural_dispatch = Mock(return_value={
            "ok": True, "glb_path": str(self.output_dir / "mesh.glb"), "size_bytes": 2000})
        self.pipeline.run_photogrammetry_dispatch = Mock(return_value={
            "ok": True, "glb_path": str(self.output_dir / "photo.glb"), "size_bytes": 2000})
        self.pipeline.run_final_acceptance = Mock(return_value={
            "ok": True, "acceptance_ok": True, "engineer_grade": 90, "threshold": 80})

    def run_pipeline(self, **kwargs):
        return self.pipeline.run_pipeline("a sphere", "regression", output_dir=self.output_dir,
                                          allow_scene=False, **kwargs)

    def test_supported_procedural_object_needs_no_cuda_or_reference_synthesis(self):
        self.pipeline.route_pipeline = Mock(return_value={"pipeline": "procedural", "procedural_template": "sphere"})
        result = self.run_pipeline()
        self.assertTrue(result["ok"])
        self.assertEqual(result["pipeline"], "procedural")
        self.assertEqual(result["run_id"], "regression")
        self.assertEqual(result["final_mesh"], self.pipeline.run_procedural_dispatch.return_value["glb_path"])
        self.pipeline.neural_engine_readiness.assert_not_called()
        self.pipeline.synth.assert_not_called()

    def test_character_does_not_degrade_to_procedural_placeholder(self):
        self.pipeline.route_pipeline = Mock(return_value={"pipeline": "procedural", "procedural_template": "humanoid"})
        result = self.run_pipeline(subject_kind_hint="character")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "neural_engine_unavailable")
        self.assertIn("CUDA indisponible", result["error"])
        self.assertNotIn("final_mesh", result)
        self.pipeline.run_procedural_dispatch.assert_not_called()
        self.pipeline.synth.assert_not_called()
        self.pipeline.synth_multiview.assert_not_called()

    def test_explicit_neural_engine_does_not_degrade_to_procedural(self):
        self.pipeline.route_pipeline = Mock(return_value={"pipeline": "procedural", "procedural_template": "sphere"})
        with patch.dict(os.environ, {"AURORA_3D_ENGINE": "trellis"}):
            result = self.run_pipeline(engine="trellis")
        self.assertFalse(result["ok"])
        self.assertEqual(set(result["readiness"]), {"trellis"})
        self.pipeline.run_procedural_dispatch.assert_not_called()

    def test_photogrammetry_dispatch_does_not_require_neural_engine(self):
        self.pipeline.route_pipeline = Mock(return_value={"pipeline": "photogrammetry"})
        result = self.run_pipeline(images=["photo1.png", "photo2.png"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["pipeline"], "photogrammetry")
        self.assertEqual(result["run_id"], "regression")
        self.assertEqual(result["final_mesh"], self.pipeline.run_photogrammetry_dispatch.return_value["glb_path"])
        self.pipeline.neural_engine_readiness.assert_not_called()

    def test_legacy_scene_result_is_normalized_for_glb_delivery(self):
        scene_glb = self.output_dir / "regression" / "scene_couleurs.glb"
        old_result = {"ok": True, "is_scene": True, "scene_glb": str(scene_glb),
                      "plan": {}, "composants": {}, "error": None}
        orchestrator = module("scene_orchestrator", orchestrate_scene=Mock(return_value=old_result))
        with patch.dict(os.environ, {"AURORA_SCENE_ORCH": "1"}), \
                patch.dict(sys.modules, {"scene_orchestrator": orchestrator}), \
                patch.object(self.pipeline, "_free_gpu_before_shape"):
            result = self.pipeline.run_pipeline("a person on a chair", "regression",
                                                output_dir=self.output_dir, allow_scene=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "aurora.pipeline.v1")
        self.assertEqual(result["run_id"], "regression")
        self.assertEqual(result["final_mesh"], str(scene_glb))
        self.assertEqual(result["scene_glb"], str(scene_glb))
        self.pipeline.neural_engine_readiness.assert_not_called()

    def test_user_reference_still_requires_a_reconstruction_engine(self):
        result = self.run_pipeline(images=["photo.png"], subject_kind_hint="character")
        self.assertFalse(result["ok"])
        self.assertEqual(result["schema"], "aurora.pipeline.v1")
        self.assertEqual(result["error_code"], "neural_engine_unavailable")
        self.pipeline.synth.assert_not_called()

    def test_healthy_engine_stages_user_reference_without_flux(self):
        self.pipeline.neural_engine_readiness = Mock(return_value={"available": True})
        stop = RuntimeError("stop at reference staging")
        with patch.object(self.pipeline, "_stage_reference_image", side_effect=stop), \
                patch.object(self.pipeline.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "{}", "")), \
                patch.dict(sys.modules, {"vlm_judge": module("vlm_judge", ask_vlm=Mock(return_value={"reconnu": False}))}):
            with self.assertRaisesRegex(RuntimeError, "stop at reference staging"):
                self.run_pipeline(images=["photo.png"], subject_kind_hint="character")
        self.pipeline.synth.assert_not_called()
        self.pipeline.synth_multiview.assert_not_called()

    def test_remote_reconstruction_can_pass_local_cuda_failure(self):
        service = module("meshy_client", joignable=Mock(return_value={"ok": True}))
        with patch.dict(os.environ, {"AURORA_MESHY": "1"}), \
                patch.dict(sys.modules, {"meshy_client": service}), \
                patch.object(self.pipeline, "enhance_flux_prompt", side_effect=RuntimeError("stop before reference generation")):
            with self.assertRaisesRegex(RuntimeError, "stop before reference generation"):
                self.run_pipeline(multi_view=False)
        service.joignable.assert_called_once()
        self.pipeline.synth.assert_not_called()

    def test_existing_mesh_does_not_require_a_cuda_engine(self):
        run_dir = self.output_dir / "regression"
        run_dir.mkdir()
        existing = run_dir / "regression_mesh.glb"
        data = b"existing mesh" * 200
        existing.write_bytes(data)
        (run_dir / "regression_reference.png").write_bytes(b"existing reference")
        self.pipeline.auto_rescue.side_effect = RuntimeError("stop after existing mesh reuse")
        with self.assertRaisesRegex(RuntimeError, "stop after existing mesh reuse"):
            self.run_pipeline(multi_view=False)
        self.assertEqual(existing.read_bytes(), data)
        self.pipeline.neural_engine_readiness.assert_not_called()
        self.pipeline.synth.assert_not_called()


class RuntimeInspectorCommandTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = pipeline_module()

    def test_check_runtime_needs_no_prompt_or_run_id_and_returns_json_when_unavailable(self):
        result = {"ok": False, "engine": "auto", "engines": {}, "remote": None,
                  "error": "CUDA indisponible"}
        output = io.StringIO()
        with patch.object(sys, "argv", ["aurora_3d_pipeline.py", "--check-runtime"]), \
                patch.object(self.pipeline, "check_neural_runtime", return_value=result) as inspector, \
                patch.object(self.pipeline, "_reexec_under_mem_scope") as scope, \
                patch.object(self.pipeline, "_freeze_sentinel") as sentinel, \
                patch.object(self.pipeline, "run_pipeline") as generator, \
                patch.object(self.pipeline.Path, "mkdir") as mkdir, \
                contextlib.redirect_stdout(output):
            exit_code = self.pipeline.main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), result)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        inspector.assert_called_once_with("auto")
        scope.assert_not_called()
        sentinel.assert_not_called()
        generator.assert_not_called()
        mkdir.assert_not_called()

    def test_check_runtime_passes_explicit_engine(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["aurora_3d_pipeline.py", "--check-runtime", "--engine", "hunyuan3d"]), \
                patch.object(self.pipeline, "check_neural_runtime", return_value={"ok": True}) as inspector, \
                contextlib.redirect_stdout(output):
            self.assertEqual(self.pipeline.main(), 0)
        inspector.assert_called_once_with("hunyuan3d")
        self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_generation_still_requires_prompt_and_run_id_before_startup(self):
        with patch.object(sys, "argv", ["aurora_3d_pipeline.py"]), \
                patch.object(self.pipeline, "_reexec_under_mem_scope") as scope, \
                patch.object(self.pipeline, "_freeze_sentinel") as sentinel, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                self.pipeline.main()
        self.assertEqual(exc.exception.code, 2)
        scope.assert_not_called()
        sentinel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
