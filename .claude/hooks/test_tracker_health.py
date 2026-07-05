"""Tests for tracker_health.compute_health — stale-task detection."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone  # noqa: F401
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from tracker_health import archive_stale, compute_health  # noqa: E402


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class HealthTests(unittest.TestCase):

    def test_empty_state_reports_zero(self):
        h = compute_health({"tasks": []})
        self.assertEqual(h["in_progress_count"], 0)
        self.assertEqual(h["stale_count"], 0)
        self.assertEqual(h["stale_tasks"], [])
        self.assertTrue(h["ok"])

    def test_in_progress_under_threshold_not_stale(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [{
            "id": "t1", "lead": "3d-quality-rescuer",
            "status": "in_progress", "started_at": _ts(now - timedelta(minutes=5)),
            "brief": "fresh task",
        }]}
        h = compute_health(state, stale_threshold_min=30, now=now)
        self.assertEqual(h["in_progress_count"], 1)
        self.assertEqual(h["stale_count"], 0)

    def test_in_progress_past_threshold_is_stale(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [{
            "id": "t1", "lead": "3d-quality-rescuer",
            "status": "in_progress", "started_at": _ts(now - timedelta(minutes=45)),
            "brief": "stuck rescue",
        }]}
        h = compute_health(state, stale_threshold_min=30, now=now)
        self.assertEqual(h["stale_count"], 1)
        self.assertEqual(h["stale_tasks"][0]["lead"], "3d-quality-rescuer")
        self.assertGreaterEqual(h["stale_tasks"][0]["age_minutes"], 45)

    def test_done_tasks_never_stale(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [{
            "id": "t1", "lead": "tunnel-validator",
            "status": "done", "started_at": _ts(now - timedelta(hours=12)),
            "finished_at": _ts(now - timedelta(hours=11)),
        }]}
        h = compute_health(state, stale_threshold_min=30, now=now)
        self.assertEqual(h["in_progress_count"], 0)
        self.assertEqual(h["stale_count"], 0)

    def test_sorted_by_age_desc(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [
            {"id": "young", "lead": "a", "status": "in_progress",
             "started_at": _ts(now - timedelta(minutes=35))},
            {"id": "ancient", "lead": "b", "status": "in_progress",
             "started_at": _ts(now - timedelta(hours=4))},
            {"id": "middle", "lead": "c", "status": "in_progress",
             "started_at": _ts(now - timedelta(minutes=90))},
        ]}
        h = compute_health(state, stale_threshold_min=30, now=now)
        self.assertEqual(h["stale_count"], 3)
        ids = [t["id"] for t in h["stale_tasks"]]
        self.assertEqual(ids, ["ancient", "middle", "young"])

    def test_missing_started_at_skipped(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [{
            "id": "t1", "lead": "3d-quality-rescuer",
            "status": "in_progress", "started_at": None,
        }]}
        h = compute_health(state, now=now)
        self.assertEqual(h["in_progress_count"], 1)  # still in flight
        self.assertEqual(h["stale_count"], 0)        # but uncountable for staleness


class ArchiveStaleTests(unittest.TestCase):

    def test_dry_run_preserves_state(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [{
            "id": "t1", "lead": "3d-quality-rescuer",
            "status": "in_progress",
            "started_at": _ts(now - timedelta(hours=6)),
            "brief": "stuck",
        }]}
        report = archive_stale(state, archive_after_min=240, now=now, dry_run=True)
        self.assertEqual(report["archived_count"], 1)
        self.assertTrue(report["dry_run"])
        # State must NOT have been mutated.
        self.assertEqual(state["tasks"][0]["status"], "in_progress")
        self.assertNotIn("auto-archived", (state["tasks"][0].get("verdict") or ""))

    def test_apply_marks_blocked_with_verdict(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [{
            "id": "t1", "lead": "3d-quality-rescuer",
            "status": "in_progress",
            "started_at": _ts(now - timedelta(hours=6)),
            "brief": "stuck",
            "verdict": None,
        }]}
        report = archive_stale(state, archive_after_min=240, now=now, dry_run=False)
        self.assertEqual(report["archived_count"], 1)
        self.assertFalse(report["dry_run"])
        t = state["tasks"][0]
        self.assertEqual(t["status"], "blocked")
        self.assertIn("auto-archived", t["verdict"])
        self.assertIsNotNone(t["finished_at"])

    def test_only_in_progress_eligible(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [
            {"id": "done", "lead": "x", "status": "done",
             "started_at": _ts(now - timedelta(hours=10))},
            {"id": "blocked", "lead": "y", "status": "blocked",
             "started_at": _ts(now - timedelta(hours=10))},
            {"id": "alive", "lead": "z", "status": "in_progress",
             "started_at": _ts(now - timedelta(minutes=10))},  # too young
        ]}
        report = archive_stale(state, archive_after_min=240, now=now, dry_run=False)
        self.assertEqual(report["archived_count"], 0)
        # All originals untouched.
        self.assertEqual(state["tasks"][0]["status"], "done")
        self.assertEqual(state["tasks"][1]["status"], "blocked")
        self.assertEqual(state["tasks"][2]["status"], "in_progress")

    def test_idempotent_second_run(self):
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        state = {"tasks": [{
            "id": "t1", "lead": "3d-quality-rescuer",
            "status": "in_progress",
            "started_at": _ts(now - timedelta(hours=6)),
        }]}
        archive_stale(state, archive_after_min=240, now=now, dry_run=False)
        # Second call: already blocked, must produce 0 archives.
        report2 = archive_stale(state, archive_after_min=240, now=now, dry_run=False)
        self.assertEqual(report2["archived_count"], 0)


if __name__ == "__main__":
    unittest.main()
