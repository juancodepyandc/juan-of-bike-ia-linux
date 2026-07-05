"""Tests for tracker_query.query — AND-semantic filtering over dispatches."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from tracker_query import query  # noqa: E402


def _t(**kwargs) -> dict:
    """Build a tracker entry with sane defaults."""
    base = {
        "id": kwargs.pop("id", "tx"),
        "lead": kwargs.pop("lead", "3d-lead"),
        "status": kwargs.pop("status", "done"),
        "started_at": kwargs.pop("started_at", "2026-04-30T10:00:00Z"),
        "finished_at": kwargs.pop("finished_at", "2026-04-30T10:01:00Z"),
        "verdict": kwargs.pop("verdict", "ok"),
        "brief": kwargs.pop("brief", ""),
    }
    if "metadata" in kwargs:
        base["metadata"] = kwargs.pop("metadata")
    return {**base, **kwargs}


class TrackerQueryTests(unittest.TestCase):

    def test_run_id_matches_metadata(self):
        tasks = [
            _t(id="t1", metadata={"run_id": "cat5"}),
            _t(id="t2", metadata={"run_id": "cat6"}),
            _t(id="t3"),  # no metadata
        ]
        r = query(run_id="cat5", tasks=tasks)
        self.assertEqual(r["match_count"], 1)
        self.assertEqual(r["tasks"][0]["id"], "t1")

    def test_run_id_falls_back_to_brief(self):
        tasks = [
            _t(id="t1", brief="auto_rescue cat7_octopus_mesh.glb"),
            _t(id="t2", brief="auto_rescue cat8_dragon_mesh.glb"),
        ]
        r = query(run_id="cat7", tasks=tasks)
        self.assertEqual(r["match_count"], 1)
        self.assertEqual(r["tasks"][0]["id"], "t1")

    def test_lead_filter(self):
        tasks = [
            _t(id="a", lead="3d-lead"),
            _t(id="b", lead="3d-quality-rescuer"),
            _t(id="c", lead="tunnel-validator"),
        ]
        r = query(lead="3d-quality-rescuer", tasks=tasks)
        self.assertEqual(r["match_count"], 1)
        self.assertEqual(r["tasks"][0]["id"], "b")

    def test_status_filter(self):
        tasks = [
            _t(id="d", status="done"),
            _t(id="b", status="blocked"),
            _t(id="i", status="in_progress"),
        ]
        r = query(status="blocked", tasks=tasks)
        self.assertEqual(r["match_count"], 1)
        self.assertEqual(r["tasks"][0]["id"], "b")

    def test_since_filter_drops_older(self):
        tasks = [
            _t(id="old", finished_at="2026-04-29T10:00:00Z"),
            _t(id="new", finished_at="2026-04-30T15:00:00Z"),
        ]
        r = query(since="2026-04-30T00:00:00Z", tasks=tasks)
        self.assertEqual(r["match_count"], 1)
        self.assertEqual(r["tasks"][0]["id"], "new")

    def test_and_semantics_across_filters(self):
        tasks = [
            _t(id="a", lead="3d-lead", status="done",
               metadata={"run_id": "x"}),
            _t(id="b", lead="3d-lead", status="blocked",
               metadata={"run_id": "x"}),
            _t(id="c", lead="3d-quality-rescuer", status="done",
               metadata={"run_id": "x"}),
            _t(id="d", lead="3d-lead", status="done",
               metadata={"run_id": "y"}),
        ]
        r = query(run_id="x", lead="3d-lead", status="done", tasks=tasks)
        self.assertEqual(r["match_count"], 1)
        self.assertEqual(r["tasks"][0]["id"], "a")

    def test_results_sorted_newest_first(self):
        tasks = [
            _t(id="a", finished_at="2026-04-30T10:00:00Z"),
            _t(id="b", finished_at="2026-04-30T15:00:00Z"),
            _t(id="c", finished_at="2026-04-30T12:00:00Z"),
        ]
        r = query(tasks=tasks)
        self.assertEqual([t["id"] for t in r["tasks"]], ["b", "c", "a"])

    def test_limit_caps_results(self):
        tasks = [_t(id=f"t{i}", finished_at=f"2026-04-30T10:0{i}:00Z")
                 for i in range(8)]
        r = query(tasks=tasks, limit=3)
        self.assertEqual(r["match_count"], 3)


if __name__ == "__main__":
    unittest.main()
