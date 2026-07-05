"""Tests for score_history.py — append/load/top/compute_trend."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_history import (  # noqa: E402
    append_event, compute_trend, load_events, top_runs,
)


def _seed(log: Path, events: list[dict]) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


class AppendLoadTests(unittest.TestCase):

    def test_append_then_load_round_trips(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "h.jsonl"
            append_event("r1", "m.glb", "creature", "initial", 70.0,
                         ["color_richness"], log_path=log)
            append_event("r1", "m_baked.glb", "creature", "after_bake", 90.0,
                         [], log_path=log)
            evts = load_events(log)
            # Newest-first by contract.
            self.assertEqual(evts[0]["stage"], "after_bake")
            self.assertEqual(evts[1]["stage"], "initial")
            self.assertEqual(evts[0]["overall_score"], 90.0)


class TopRunsTests(unittest.TestCase):

    def test_top_orders_by_final_score_desc(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "h.jsonl"
            _seed(log, [
                {"run_id": "low", "subject_kind": "creature",
                 "stage": "initial", "overall_score": 50.0,
                 "failed_axes": [], "ts": "2026-04-01T00:00:00Z"},
                {"run_id": "low", "subject_kind": "creature",
                 "stage": "after_bake", "overall_score": 60.0,
                 "failed_axes": [], "ts": "2026-04-01T00:01:00Z"},
                {"run_id": "high", "subject_kind": "pc_tower",
                 "stage": "initial", "overall_score": 80.0,
                 "failed_axes": [], "ts": "2026-04-01T00:02:00Z"},
                {"run_id": "high", "subject_kind": "pc_tower",
                 "stage": "after_bake", "overall_score": 95.0,
                 "failed_axes": [], "ts": "2026-04-01T00:03:00Z"},
            ])
            rows = top_runs(log)
            self.assertEqual(rows[0]["run_id"], "high")
            self.assertEqual(rows[0]["final_score"], 95.0)
            self.assertEqual(rows[0]["score_delta"], 15.0)


class TrendTests(unittest.TestCase):

    def test_empty_log_returns_zero_trend(self):
        with tempfile.TemporaryDirectory() as td:
            t = compute_trend(Path(td) / "missing.jsonl")
            self.assertEqual(t["total_events"], 0)
            self.assertEqual(t["promoted_runs"], 0)
            self.assertEqual(t["promote_rate"], 0.0)
            self.assertEqual(t["axis_lifts"], {})

    def test_aggregates_promote_rate_and_axis_lifts(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "h.jsonl"
            _seed(log, [
                # run A: lifts color_richness (initial→final) — promoted
                {"run_id": "A", "subject_kind": "creature",
                 "stage": "initial", "overall_score": 50.0,
                 "failed_axes": ["color_richness"], "ts": "2026-04-01T00:00:00Z"},
                {"run_id": "A", "subject_kind": "creature",
                 "stage": "after_bake", "overall_score": 90.0,
                 "failed_axes": [], "ts": "2026-04-01T00:01:00Z"},
                # run B: no axes lifted, score same — not promoted
                {"run_id": "B", "subject_kind": "pc_tower",
                 "stage": "initial", "overall_score": 80.0,
                 "failed_axes": ["silhouette_aspect"], "ts": "2026-04-01T00:02:00Z"},
                {"run_id": "B", "subject_kind": "pc_tower",
                 "stage": "after_bake", "overall_score": 80.0,
                 "failed_axes": ["silhouette_aspect"], "ts": "2026-04-01T00:03:00Z"},
                # run C: lifts both color + aspect — promoted
                {"run_id": "C", "subject_kind": "pc_tower",
                 "stage": "initial", "overall_score": 60.0,
                 "failed_axes": ["color_richness", "silhouette_aspect"],
                 "ts": "2026-04-01T00:04:00Z"},
                {"run_id": "C", "subject_kind": "pc_tower",
                 "stage": "after_bake", "overall_score": 96.0,
                 "failed_axes": [], "ts": "2026-04-01T00:05:00Z"},
            ])
            t = compute_trend(log)
            self.assertEqual(t["total_runs"], 3)
            self.assertEqual(t["promoted_runs"], 2)
            self.assertAlmostEqual(t["promote_rate"], round(2 / 3, 3))
            self.assertEqual(t["best_delta"], 40.0)
            self.assertEqual(t["axis_lifts"]["color_richness"], 2)
            self.assertEqual(t["axis_lifts"]["silhouette_aspect"], 1)
            self.assertEqual(t["kind_breakdown"]["pc_tower"], 2)
            self.assertEqual(t["kind_breakdown"]["creature"], 1)


if __name__ == "__main__":
    unittest.main()
