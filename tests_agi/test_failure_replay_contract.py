"""Keep runtime audits and held-out subjects outside training replay."""

from pathlib import Path
import tempfile
import unittest

from auto_rl.failure_memory import record_failure, replay_tasks
from auto_rl.storage import read_json


class FailureReplayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)

    def test_audit_failures_never_enter_training_memory(self):
        self.assertFalse(record_failure(self.state, "code", {"split": "audit", "prompt": "private audit"}))
        self.assertFalse((self.state / "failure_memory/code.json").exists())

    def test_training_failure_is_persisted_and_replayed_without_changing_audit(self):
        task = {"id": "failure", "family": "edge_case", "prompt": "observed failure", "split": "train"}
        for score in (0.4, 0.2):
            self.assertTrue(record_failure(self.state, "code", task, {"judge": {"score": score}}))
        entries = read_json(self.state / "failure_memory/code.json", [])
        self.assertEqual(entries[0]["attempts"], 2)
        self.assertEqual(entries[0]["worst_score"], 0.2)
        tasks = [{"id": str(i), "family": f"family_{i}", "prompt": str(i),
                  "split": "train" if i < 4 else "audit"} for i in range(6)]
        replayed = replay_tasks(tasks, {"module": "code", "train_tasks": 4, "failure_replay_tasks": 2}, self.state)
        self.assertEqual(replayed[4:], tasks[4:])
        self.assertEqual(len(replayed), len(tasks))
        self.assertEqual(sum(t.get("origin") == "observed_failure_replay" for t in replayed[:4]), 1)
        self.assertTrue(all(t["split"] == "train" for t in replayed[:4]))


if __name__ == "__main__":
    unittest.main()
