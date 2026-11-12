from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from agi_core.judge_ratchet import judge_ratchet


class RatchetPersistence(unittest.TestCase):
    def test_concurrent_increments_preserve_metadata_and_strict_evidence_growth(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratchet.json"
            path.write_text(json.dumps({"ratchet_level": 641, "history_runs": 567, "provenance": "preserved"}))
            before = judge_ratchet(path=path)
            with ThreadPoolExecutor(max_workers=4) as pool:
                states = list(pool.map(lambda _: judge_ratchet(advance=True, path=path), range(20)))
            self.assertEqual(sorted(s["ratchet_level"] for s in states), list(range(642, 662)))
            after = judge_ratchet(path=path)
            self.assertEqual(after["history_runs"], 587)
            self.assertEqual(after["provenance"], "preserved")
            self.assertGreater(after["required_holdout_cases"], before["required_holdout_cases"])
            self.assertLess(after["max_error_probability"], before["max_error_probability"])

    def test_corrupt_state_is_never_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratchet.json"
            for invalid in ('{"ratchet_level":true}', '{broken', '[]'):
                path.write_text(invalid)
                with self.assertRaises(ValueError):
                    judge_ratchet(advance=True, path=path)
                self.assertEqual(path.read_text(), invalid)

    def test_growing_evidence_floor_cannot_be_satisfied_by_repeating_a_case(self):
        from agi_core.judge_ratchet import judge_independent_holdout_evidence
        ratchet = {"ratchet_level": 76, "required_holdout_cases": 2}
        first = {"case_sha256": "a" * 64, "receipt_sha256": "b" * 64,
                 "independent_holdout": True, "executed": True, "passed": True}
        second = {**first, "case_sha256": "c" * 64}
        self.assertFalse(judge_independent_holdout_evidence([], ratchet=ratchet)["passed"])
        self.assertFalse(judge_independent_holdout_evidence([first, first], ratchet=ratchet)["passed"])
        self.assertTrue(judge_independent_holdout_evidence([first, second], ratchet=ratchet)["passed"])
        harder = {"ratchet_level": 77, "required_holdout_cases": 3}
        self.assertFalse(judge_independent_holdout_evidence([first, second], ratchet=harder)["passed"])
