import tempfile
import unittest
from pathlib import Path

from video_ab_benchmark import (
    build_variant_command,
    measured_score,
    normalize_spec,
    run_benchmark,
)


class VideoAbBenchmarkTests(unittest.TestCase):
    def test_same_contract_is_used_for_every_engine(self):
        spec = normalize_spec({
            "prompt": "A red robot walks through a rainy street.",
            "seed": 77,
            "width": 832,
            "height": 480,
            "num_frames": 49,
            "variants": ["wan5b", "ltx"],
        })
        first = build_variant_command(spec, "wan5b", Path("/tmp/wan.mp4"))
        second = build_variant_command(spec, "ltx", Path("/tmp/ltx.mp4"))
        for flag in ("--prompt", "--seed", "--width", "--height", "--num_frames", "--negative_prompt"):
            self.assertEqual(first[first.index(flag) + 1], second[second.index(flag) + 1])
        self.assertNotEqual(
            first[first.index("--force_strategy") + 1],
            second[second.index("--force_strategy") + 1],
        )

    def test_unmeasured_vision_never_selects_a_score(self):
        score, coverage = measured_score(
            {
                "score": None,
                "physics_score": None,
                "identity_score": None,
                "action_score": None,
            },
            {"ok": True},
        )
        self.assertIsNone(score)
        self.assertEqual(coverage, 0.2)

    def test_plan_only_does_not_launch_a_render(self):
        spec = normalize_spec({
            "prompt": "A ceramic bird turns its head.",
            "variants": ["wan5b", "ltx"],
        })
        with tempfile.TemporaryDirectory() as tmp:
            result = run_benchmark(spec, Path(tmp), plan_only=True)
        self.assertTrue(result["ok"])
        self.assertTrue(result["plan_only"])
        self.assertEqual(len(result["commands"]), 2)


if __name__ == "__main__":
    unittest.main()
