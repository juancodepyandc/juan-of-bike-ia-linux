"""CPU-only regression tests for honest cinema quality accounting."""

from __future__ import annotations

import json
import unittest
import tempfile
from unittest.mock import patch

import numpy as np
from PIL import Image

from cinema_pipeline import (
    _dialogue_audio_detected,
    _laplacian_variance,
    _compute_quality_grade,
    check_audio_silence,
    check_temporal_coherence,
    dedupe_shot_quality,
    plan_shot_segments,
    probe_render_truth,
    select_anchor_character,
    shot_quality_ok,
)
from storyboard_norm import MAX_SHOT_S, MIN_SHOT_S, normalize_storyboard


def measured_shot(shot_id: int = 1, score: int = 9) -> dict:
    return {
        "shot_id": shot_id,
        "score": score,
        "physics_score": score,
        "identity_score": score,
        "action_score": score,
        "graded": True,
        "issues": [],
    }


class CinemaQualityTests(unittest.TestCase):
    def test_missing_measurements_never_pass_gate(self):
        self.assertFalse(shot_quality_ok({
            "score": None,
            "physics_score": None,
            "identity_score": None,
            "action_score": None,
            "graded": False,
            "issues": ["vision JSON parse failed; validation skipped"],
        }, "premium"))

    def test_dedupe_keeps_worst_measurement(self):
        result = dedupe_shot_quality([
            measured_shot(score=9),
            measured_shot(score=5),
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["score"], 5)

    def test_dedupe_prefers_real_measurement_over_parse_failure(self):
        ungraded = {
            "shot_id": 1,
            "score": None,
            "physics_score": None,
            "identity_score": None,
            "action_score": None,
            "graded": False,
        }
        measured = measured_shot(score=7)
        result = dedupe_shot_quality([ungraded, measured])
        self.assertEqual(result, [measured])

    def test_unmeasured_qa_is_not_exportable(self):
        grade = _compute_quality_grade(
            [{
                "shot_id": 1,
                "score": None,
                "physics_score": None,
                "identity_score": None,
                "action_score": None,
                "graded": False,
            }],
            [],
            [],
            {"ok": True},
            {},
        )
        self.assertEqual(grade["grade"], "D")
        self.assertFalse(grade["exportable"])
        self.assertLess(grade["coverage"]["overall_pct"], 50)

    def test_fully_measured_excellent_shot_is_exportable(self):
        grade = _compute_quality_grade(
            [measured_shot(score=9)],
            [],
            [{"shot_id": 1, "ok": True}],
            {"ok": True},
            {},
        )
        self.assertEqual(grade["grade"], "A")
        self.assertTrue(grade["exportable"])
        self.assertEqual(grade["coverage"]["overall_pct"], 100.0)

    def test_failed_action_dimension_cannot_average_into_grade_a(self):
        shot = measured_shot(score=10)
        shot.update({"score": 7, "action_score": 5})
        grade = _compute_quality_grade(
            [shot],
            [{"shot_id": 1, "ok": True}],
            [{"shot_id": 1, "ok": True}],
            {"ok": True},
            {"Testeur": {"score": 10}},
        )
        self.assertEqual(grade["grade"], "C")
        self.assertFalse(grade["exportable"])
        self.assertEqual(
            grade["weak_shots"][0]["failed_dimensions"],
            ["action_score"],
        )

    def test_missing_media_never_becomes_a_passing_measurement(self):
        temporal = check_temporal_coherence("/tmp/aurora-video-does-not-exist.mp4")
        audio = check_audio_silence(
            "/tmp/aurora-video-does-not-exist.mp4",
            expected_duration_s=2.0,
            expected_dialogue=True,
        )
        self.assertIsNone(temporal["ok"])
        self.assertFalse(temporal["graded"])
        self.assertIsNone(audio["ok"])
        self.assertFalse(audio["graded"])

    def test_laplacian_anchor_score_prefers_a_sharp_frame(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            flat_path = f"{temp_dir}/flat.png"
            sharp_path = f"{temp_dir}/sharp.png"
            flat = np.full((64, 64), 127, dtype=np.uint8)
            sharp = np.indices((64, 64)).sum(axis=0) % 2 * 255
            Image.fromarray(flat).save(flat_path)
            Image.fromarray(sharp.astype(np.uint8)).save(sharp_path)
            self.assertGreater(
                _laplacian_variance(sharp_path),
                _laplacian_variance(flat_path),
            )

    def test_long_segments_cover_duration_on_common_wan_ltx_grid(self):
        for seconds in (4.1, 8.0, 16.0, 20.2):
            with self.subTest(seconds=seconds):
                segments = plan_shot_segments(seconds)
                self.assertLessEqual(len(segments), 5)
                self.assertGreaterEqual(sum(segments), round(seconds * 24))
                self.assertTrue(all(25 <= frames <= 97 for frames in segments))
                self.assertTrue(all((frames - 1) % 8 == 0 for frames in segments))

    def test_render_truth_keeps_worker_native_dimensions_and_frames(self):
        probe_payload = json.dumps({
            "streams": [{
                "width": 1280,
                "height": 720,
                "r_frame_rate": "24/1",
                "nb_read_frames": "65",
            }],
        })
        native_shots = [{
            "shot_id": 1,
            "segment": 1,
            "model": "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
            "strategy": "wan5b-i2v-primary",
            "native_width": 832,
            "native_height": 480,
            "native_frames": 65,
        }]
        with patch("cinema_pipeline._run", return_value=(0, probe_payload, "")):
            truth = probe_render_truth(
                "/tmp/result.mp4",
                native_width=832,
                native_height=480,
                native_frames=65,
                native_shots=native_shots,
                postprocess_chain=["ffmpeg_minterpolate_24_to_48", "shot_concat"],
            )
        self.assertEqual(truth["native_width"], 832)
        self.assertEqual(truth["native_frames"], 65)
        self.assertEqual(truth["delivered_width"], 1280)
        self.assertEqual(truth["native_shots"], native_shots)

    def test_short_dialogue_with_natural_padding_is_not_false_silence(self):
        self.assertTrue(_dialogue_audio_detected(
            has_audio=True,
            expected_duration_s=2.65,
            total_silence_s=1.8,
        ))
        self.assertFalse(_dialogue_audio_detected(
            has_audio=True,
            expected_duration_s=10.0,
            total_silence_s=9.7,
        ))
        self.assertFalse(_dialogue_audio_detected(
            has_audio=False,
            expected_duration_s=2.65,
            total_silence_s=0.0,
        ))

    def test_medium_simple_studio_shot_uses_identity_anchor(self):
        characters = {"Testeur": {"description": "adult technician"}}
        keyframes = {"Testeur": "/tmp/testeur.png"}
        name, path = select_anchor_character({
            "scene": "Medium shot of Testeur in a softly lit film studio.",
            "camera": "medium shot, locked camera",
            "dialogue": "Test réussi.",
        }, "Testeur", characters, keyframes)
        self.assertEqual((name, path), ("Testeur", "/tmp/testeur.png"))

    def test_incidental_hand_gesture_does_not_disable_identity_anchor(self):
        characters = {"Testeur": {"description": "adult technician"}}
        keyframes = {"Testeur": "/tmp/testeur.png"}
        name, path = select_anchor_character({
            "scene": (
                "Medium shot of Testeur in a softly lit film studio, "
                "making one small natural hand gesture toward the camera."
            ),
            "camera": "medium shot, locked camera",
            "dialogue": "Test réussi.",
        }, "Testeur", characters, keyframes)
        self.assertEqual((name, path), ("Testeur", "/tmp/testeur.png"))

    def test_explicit_hand_closeup_stays_unanchored(self):
        characters = {"Testeur": {"description": "adult technician"}}
        keyframes = {"Testeur": "/tmp/testeur.png"}
        name, path = select_anchor_character({
            "scene": "Close-up detail shot of Testeur's hand opening a lock.",
            "camera": "close-up",
        }, "Testeur", characters, keyframes)
        self.assertEqual((name, path), ("", None))

    def test_wide_complex_scene_does_not_leak_portrait_backdrop(self):
        characters = {"Testeur": {"description": "adult technician"}}
        keyframes = {"Testeur": "/tmp/testeur.png"}
        name, path = select_anchor_character({
            "scene": "Wide shot of Testeur on a stormy boat at sea.",
            "camera": "wide establishing shot",
            "dialogue": "Attention.",
            "identity_priority": True,
        }, "Testeur", characters, keyframes)
        self.assertEqual((name, path), ("", None))


class StoryboardNormalizationTests(unittest.TestCase):
    def test_dialogue_extends_shot_and_inherits_location(self):
        payload = normalize_storyboard({
            "characters": [],
            "shots": [
                {"id": 1, "duration_s": 3, "location": "atelier", "scene": "Vue large."},
                {
                    "id": 2,
                    "duration_s": 2,
                    "scene": "Gros plan.",
                    "dialogue": "un deux trois quatre cinq six sept huit neuf dix",
                },
            ],
        })
        self.assertEqual(payload["quality_mode"], "balanced")
        self.assertEqual(payload["shots"][1]["location"], "atelier")
        self.assertGreater(payload["shots"][1]["duration_s"], 2)
        self.assertIn("duration_adjusted", payload["shots"][1])

    def test_invalid_and_extreme_durations_are_bounded(self):
        payload = normalize_storyboard({
            "shots": [
                {"duration_s": "invalid", "scene": "A"},
                {"duration_s": 999, "scene": "B"},
                {"duration_s": 0.1, "scene": "C"},
            ],
        })
        durations = [shot["duration_s"] for shot in payload["shots"]]
        self.assertTrue(all(MIN_SHOT_S <= value <= MAX_SHOT_S for value in durations))
        self.assertEqual(durations[1], MAX_SHOT_S)
        self.assertEqual(durations[2], MIN_SHOT_S)


if __name__ == "__main__":
    unittest.main()
