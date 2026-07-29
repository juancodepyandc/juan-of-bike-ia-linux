"""Tests CPU purs des contrats critiques de video_generate.py."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = pathlib.Path(__file__).with_name("video_generate.py")
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("aurora_video_generate", MODULE_PATH)
assert SPEC and SPEC.loader
VIDEO_GENERATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIDEO_GENERATE)


class WorkerContractTests(unittest.TestCase):
    def test_seed_negative_and_interpolation_cross_process_boundary(self):
        args = argparse.Namespace(
            seed=4_242,
            negative_prompt="wrong costume, identity drift",
            motion_interp="0",
        )
        strategy = {"id": "test", "num_frames": 25}

        config = VIDEO_GENERATE.build_worker_config(
            args,
            prompt="A stable character walks through frame.",
            output_path="/tmp/test.mp4",
            image_path="/tmp/ref.png",
            thumbnail_path="/tmp/thumb.png",
            mode="i2v",
            model_id="Wan-AI/test",
            strategy=strategy,
        )

        self.assertEqual(config["seed"], 4_242)
        self.assertEqual(
            config["negative_prompt"],
            "wrong costume, identity drift",
        )
        self.assertEqual(config["motion_interp"], "0")
        self.assertIs(config["strategy"], strategy)

    def test_optional_controls_have_honest_defaults(self):
        config = VIDEO_GENERATE.build_worker_config(
            argparse.Namespace(),
            prompt="prompt",
            output_path="/tmp/test.mp4",
            image_path=None,
            thumbnail_path=None,
            mode="t2v",
            model_id="Wan-AI/test",
            strategy={"id": "test"},
        )

        self.assertIsNone(config["seed"])
        self.assertIsNone(config["negative_prompt"])
        self.assertEqual(config["motion_interp"], "1")

    def test_managed_cold_model_fails_honestly_when_mount_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            manifest = root / "storage_manifest.json"
            manifest.write_text(json.dumps({
                "mount_path": str(root / "cold"),
                "entries": [{
                    "id": "wan",
                    "tier": "cold",
                    "hot_path": str(root / "hot" / "models--Wan-AI--Test"),
                    "cold_path": str(root / "cold" / "hf" / "models--Wan-AI--Test"),
                }],
            }), encoding="utf-8")
            with patch.object(VIDEO_GENERATE.os.path, "ismount", return_value=False):
                ok, reason = VIDEO_GENERATE.managed_model_storage_access(
                    "Wan-AI/Test",
                    str(manifest),
                )
        self.assertFalse(ok)
        self.assertEqual(reason, "cold_storage_offline")

    def test_unmanaged_model_is_not_blocked_by_storage_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = pathlib.Path(tmp) / "storage_manifest.json"
            manifest.write_text('{"entries":[]}', encoding="utf-8")
            ok, reason = VIDEO_GENERATE.managed_model_storage_access(
                "Example/Personal-Quality-Candidate",
                str(manifest),
            )
        self.assertTrue(ok)
        self.assertEqual(reason, "unmanaged")

    def test_ab_force_keeps_only_requested_engine(self):
        strategies = [
            {
                "id": "wan5b-t2v-primary",
                "family": "wan",
                "model_override": VIDEO_GENERATE.WAN_TI2V_5B_MODEL,
            },
            {"id": "ltx-t2v-safety", "family": "ltx"},
            {"id": "ltx-t2v-lowmem", "family": "ltx"},
        ]
        wan = VIDEO_GENERATE.select_forced_strategies(strategies, "wan5b")
        ltx = VIDEO_GENERATE.select_forced_strategies(strategies, "ltx")
        self.assertEqual([item["id"] for item in wan], ["wan5b-t2v-primary"])
        self.assertEqual(
            [item["id"] for item in ltx],
            ["ltx-t2v-safety", "ltx-t2v-lowmem"],
        )

    def test_final_gguf_floor_is_q8(self):
        self.assertEqual(VIDEO_GENERATE.WAN_GGUF_QUANT_DEFAULT, "Q8_0")

    def test_unified_wan_ti2v_uses_image_pipeline_when_anchored(self):
        self.assertTrue(VIDEO_GENERATE.use_wan_image_pipeline(
            "i2v",
            VIDEO_GENERATE.WAN_TI2V_5B_MODEL,
        ))
        self.assertFalse(VIDEO_GENERATE.use_wan_image_pipeline(
            "t2v",
            VIDEO_GENERATE.WAN_TI2V_5B_MODEL,
        ))

    def test_quick_clip_keeps_8_and_16_second_requests_for_segmentation(self):
        self.assertEqual(VIDEO_GENERATE.normalize_requested_frames(8 * 24), 192)
        self.assertEqual(VIDEO_GENERATE.normalize_requested_frames(16 * 24), 384)
        self.assertEqual(
            VIDEO_GENERATE.normalize_requested_frames(10_000),
            VIDEO_GENERATE.VIDEO_LONG_MAX_FRAMES,
        )

    def test_single_segment_uses_common_wan_ltx_frame_grid(self):
        self.assertEqual(VIDEO_GENERATE.normalize_model_frames(25), 25)
        self.assertEqual(VIDEO_GENERATE.normalize_model_frames(48), 49)
        self.assertEqual(VIDEO_GENERATE.normalize_model_frames(96), 97)
        self.assertEqual(VIDEO_GENERATE.normalize_model_frames(97), 97)

    def test_recovery_strategies_never_shorten_requested_frames(self):
        for mode in ("t2v", "i2v"):
            for vram in (6.0, 10.0, 16.0, 24.0):
                with self.subTest(mode=mode, vram=vram):
                    strategies = VIDEO_GENERATE.build_strategies(
                        mode,
                        1280,
                        704,
                        89,
                        vram_gb=vram,
                        quality_mode="premium",
                    )
                    self.assertTrue(strategies)
                    self.assertTrue(all(item["num_frames"] == 89 for item in strategies))

    def test_segmented_parent_reports_real_long_clip_contract(self):
        import cinema.cinema_pipeline as cinema_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            output = root / "long.mp4"
            args = argparse.Namespace(
                output=str(output),
                prompt="A continuous precise camera move.",
                image=None,
                negative_prompt="identity drift",
                seed=123,
                motion_interp="2",
                force_strategy="wan5b",
                quality_mode="premium",
                thumbnail=None,
            )

            def fake_render(**kwargs):
                pathlib.Path(kwargs["output_mp4"]).write_bytes(b"video")
                return {
                    "ok": True,
                    "segments": 4,
                    "models": ["Wan-AI/test"],
                    "strategies": ["wan5b-test"],
                    "anchor_strategy": "sharpest_laplacian_tail_frame",
                    "warnings": [],
                    "segment_results": [
                        {
                            "model": "Wan-AI/test",
                            "strategy": "wan5b-test",
                            "render_truth": {
                                "native_width": 640,
                                "native_height": 384,
                                "delivered_fps": 60,
                                "native_frames": 97,
                            },
                            "validation": {"ok": True},
                        }
                        for _ in range(4)
                    ],
                }

            stdout = io.StringIO()
            with (
                patch.object(cinema_pipeline, "render_long_shot", side_effect=fake_render) as render_mock,
                patch.object(cinema_pipeline, "probe_video_duration", return_value=16.0),
                contextlib.redirect_stdout(stdout),
            ):
                VIDEO_GENERATE.run_segmented_parent(
                    args,
                    width=640,
                    height=384,
                    requested_frames=384,
                    raw_requested_frames=384,
                )

            payload = json.loads(stdout.getvalue().strip().splitlines()[-1])
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["render_truth"]["native_frames"], 388)
            self.assertEqual(payload["render_truth"]["planned_frames"], 384)
            self.assertEqual(payload["render_truth"]["segments"], 4)
            self.assertEqual(payload["render_truth"]["delivered_fps"], 60)
            call = render_mock.call_args.kwargs
            self.assertEqual(call["duration_s"], 16.0)
            self.assertEqual(call["motion_interp"], "2")
            self.assertEqual(call["force_strategy"], "wan5b")


if __name__ == "__main__":
    unittest.main()
