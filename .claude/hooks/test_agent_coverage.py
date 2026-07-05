"""Tests for agent_coverage.compute_coverage — declared vs dispatched."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_coverage import compute_coverage  # noqa: E402


def _state(tasks: list[dict] | None = None,
           leads: dict | None = None,
           crosscut: list[str] | None = None) -> dict:
    return {
        "schema_version": "aurora.tracker.v1",
        "tasks": tasks or [],
        "leads": leads or {},
        "crosscut": crosscut or [],
    }


class CoverageTests(unittest.TestCase):

    def test_dead_set_includes_zero_dispatch_agents(self):
        # Patch _declared_agents to return a known list, and _collect_dispatches
        # to return only one of them as having dispatches.
        with mock.patch("agent_coverage._declared_agents",
                        return_value=["a", "b", "c"]), \
             mock.patch("agent_coverage._collect_dispatches",
                        return_value={"a": [{"finished_at": "2026-04-30T10:00:00Z"}]}):
            cov = compute_coverage(_state(leads={"a": {"sub_agents": ["b"]},
                                                 "c": {"sub_agents": []}}))
            self.assertEqual(cov["total_declared"], 3)
            self.assertEqual(cov["total_dispatched"], 1)
            self.assertEqual(cov["total_dead"], 2)
            self.assertIn("b", cov["dead"])
            self.assertIn("c", cov["dead"])
            self.assertNotIn("a", cov["dead"])

    def test_role_assignment(self):
        with mock.patch("agent_coverage._declared_agents",
                        return_value=["3d-lead", "3d-quality-rescuer", "tunnel-validator"]), \
             mock.patch("agent_coverage._collect_dispatches", return_value={}):
            cov = compute_coverage(_state(
                leads={"3d-lead": {"sub_agents": ["3d-quality-rescuer"]}},
                crosscut=["tunnel-validator"],
            ))
            roles = {r["name"]: r["role"] for r in cov["by_lead"]}
            self.assertEqual(roles["3d-lead"], "lead")
            self.assertEqual(roles["3d-quality-rescuer"], "sub")
            self.assertEqual(roles["tunnel-validator"], "crosscut")

    def test_sub_carries_parent_lead(self):
        with mock.patch("agent_coverage._declared_agents",
                        return_value=["3d-lead", "3d-quality-rescuer"]), \
             mock.patch("agent_coverage._collect_dispatches", return_value={}):
            cov = compute_coverage(_state(
                leads={"3d-lead": {"sub_agents": ["3d-quality-rescuer"]}}))
            sub = next(r for r in cov["by_lead"] if r["name"] == "3d-quality-rescuer")
            self.assertEqual(sub["parent_lead"], "3d-lead")

    def test_sorted_by_dispatch_count_desc_then_name(self):
        with mock.patch("agent_coverage._declared_agents",
                        return_value=["zebra", "alpha", "beta"]), \
             mock.patch("agent_coverage._collect_dispatches",
                        return_value={"alpha": [{}, {}], "beta": [{}, {}]}):
            cov = compute_coverage(_state())
            order = [r["name"] for r in cov["by_lead"]]
            # alpha and beta have 2 each → alphabetical, then zebra (0).
            self.assertEqual(order, ["alpha", "beta", "zebra"])

    def test_coverage_pct_rounds(self):
        names = [f"agent{i}" for i in range(10)]
        with mock.patch("agent_coverage._declared_agents", return_value=names), \
             mock.patch("agent_coverage._collect_dispatches",
                        return_value={"agent0": [{}]}):
            cov = compute_coverage(_state())
            # 1 / 10 = 10.0%.
            self.assertEqual(cov["coverage_pct"], 10.0)
            self.assertEqual(cov["total_dispatched"], 1)
            self.assertEqual(cov["total_dead"], 9)

    def test_last_dispatch_at_picks_max_timestamp(self):
        with mock.patch("agent_coverage._declared_agents", return_value=["x"]), \
             mock.patch("agent_coverage._collect_dispatches",
                        return_value={"x": [
                            {"finished_at": "2026-04-30T05:00:00Z"},
                            {"finished_at": "2026-04-30T15:00:00Z"},
                            {"finished_at": "2026-04-30T10:00:00Z"},
                        ]}):
            cov = compute_coverage(_state())
            row = next(r for r in cov["by_lead"] if r["name"] == "x")
            self.assertEqual(row["last_dispatch_at"], "2026-04-30T15:00:00Z")


if __name__ == "__main__":
    unittest.main()
