import unittest

from video_model_watch import build_report, detect_official_wan27


class VideoModelWatchTests(unittest.TestCase):
    def test_wan27_requires_exact_official_owner(self):
        result = detect_official_wan27([
            {"modelId": "random-user/Wan2.7-GGUF"},
            {"modelId": "Wan-AI/Wan2.2-TI2V-5B"},
        ])
        self.assertFalse(result["verified"])
        self.assertEqual(result["decision"], "no_official_wan2.7_weights_found")

    def test_official_wan27_is_detected_without_aliasing(self):
        result = detect_official_wan27([
            {"modelId": "Wan-AI/Wan2.7-I2V-A14B"},
        ])
        self.assertTrue(result["verified"])
        self.assertEqual(result["official_model_ids"], ["Wan-AI/Wan2.7-I2V-A14B"])

    def test_network_failures_reduce_coverage_instead_of_inventing_release(self):
        def fake_fetch(url: str, _timeout: float):
            if "api/models?" in url:
                raise TimeoutError("offline")
            if "api.github.com" in url:
                return {
                    "full_name": "owner/repo",
                    "default_branch": "main",
                    "pushed_at": "2026-07-26T00:00:00Z",
                    "updated_at": "2026-07-26T00:00:00Z",
                    "license": {"spdx_id": "MIT"},
                }
            return {
                "modelId": "example/model",
                "sha": "abc",
                "lastModified": "2026-07-26T00:00:00Z",
                "tags": ["license:mit"],
                "siblings": [],
            }

        report = build_report(fetcher=fake_fetch, timeout=2.0)
        self.assertTrue(report["ok"])
        self.assertFalse(report["coverage"]["complete"])
        self.assertIsNone(report["wan2.7"]["verified"])
        self.assertEqual(
            report["wan2.7"]["decision"],
            "official_source_unreachable_no_conclusion",
        )


if __name__ == "__main__":
    unittest.main()
