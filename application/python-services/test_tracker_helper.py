"""Tests for tracker_helper.record_dispatch — append-side tracker writes."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from tracker_helper import record_dispatch  # noqa: E402


class RecordDispatchTests(unittest.TestCase):

    def test_creates_state_file_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            entry = record_dispatch(
                "3d-quality-rescuer",
                "auto_rescue test.glb",
                verdict="ok",
                tracker_path=target,
            )
            self.assertIsNotNone(entry)
            self.assertEqual(entry["lead"], "3d-quality-rescuer")
            self.assertEqual(entry["status"], "done")
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(data["tasks"]), 1)
            self.assertEqual(data["tasks"][0]["lead"], "3d-quality-rescuer")

    def test_appends_to_existing_state(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            target.write_text(json.dumps({
                "schema_version": "aurora.tracker.v1",
                "tasks": [{"id": "t0", "lead": "tunnel-validator",
                           "status": "done"}],
                "leads": {},
            }), encoding="utf-8")
            record_dispatch("3d-quality-rescuer", "rescue cat5",
                            tracker_path=target)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(data["tasks"]), 2)
            self.assertEqual(data["tasks"][-1]["lead"], "3d-quality-rescuer")

    def test_blocked_dispatch_records_verdict(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            entry = record_dispatch(
                "3d-quality-rescuer",
                "auto_rescue missing.glb",
                status="blocked",
                verdict="mesh not found",
                tracker_path=target,
            )
            self.assertEqual(entry["status"], "blocked")
            self.assertEqual(entry["verdict"], "mesh not found")

    def test_truncates_oversized_brief(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            very_long = "x" * 1000
            entry = record_dispatch(
                "3d-quality-rescuer",
                very_long,
                tracker_path=target,
            )
            self.assertLess(len(entry["brief"]), 250)
            self.assertTrue(entry["brief"].endswith("…"))

    def test_metadata_round_trips(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            entry = record_dispatch(
                "3d-quality-rescuer", "rescue cat6",
                metadata={
                    "run_id": "cat6", "kind": "creature",
                    "score_delta": 23.4, "final_failed_axes": [],
                },
                tracker_path=target,
            )
            self.assertEqual(entry["metadata"]["run_id"], "cat6")
            self.assertEqual(entry["metadata"]["score_delta"], 23.4)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["tasks"][0]["metadata"]["kind"], "creature")

    def test_metadata_drops_unserializable_values(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"

            class NotJsonable:
                pass

            entry = record_dispatch(
                "3d-lead", "pipeline",
                metadata={"run_id": "ok", "bad": NotJsonable(), "kind": "creature"},
                tracker_path=target,
            )
            self.assertIn("run_id", entry["metadata"])
            self.assertIn("kind", entry["metadata"])
            self.assertNotIn("bad", entry["metadata"])

    def test_omitted_metadata_yields_no_field(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            entry = record_dispatch("tunnel-validator", "ping",
                                    tracker_path=target)
            self.assertNotIn("metadata", entry)


if __name__ == "__main__":
    unittest.main()
