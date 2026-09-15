import tempfile
import unittest
from pathlib import Path

from auto_rl.config import defaults
from auto_rl.failure_memory import record_failure, replay_tasks
from auto_rl.storage import read_json


class FailureMemoryTests(unittest.TestCase):
    def test_training_failure_is_replayed_and_audit_order_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="aurora-rl-test-") as directory:
            state = Path(directory)
            config = defaults("conversation")
            config.update(state_dir=str(state), train_tasks=3, eval_tasks=2, failure_replay_tasks=1)
            failed = {"id": "train_old", "split": "train", "family": "old",
                      "prompt": "solve the difficult case"}
            record_failure(state, "conversation", failed,
                           {"judge": {"score": 0.0, "valid": True, "metrics": {}}},
                           run_id="old-run")
            entries = read_json(state / "failure_memory/conversation.json")
            self.assertEqual(len(entries), 1)
            tasks = [failed, {"id": "train_regular", "split": "train", "family": "regular", "prompt": "regular"},
                     {"id": "train_regular2", "split": "train", "family": "regular2", "prompt": "regular 2"},
                     {"id": "audit_holdout", "split": "audit", "family": "heldout", "prompt": "audit"},
                     {"id": "audit_holdout2", "split": "audit", "family": "heldout2", "prompt": "audit 2"}]
            replayed = replay_tasks(tasks, config, state)
            self.assertEqual(replayed[0]["origin"], "observed_failure_replay")
            self.assertEqual(replayed[0]["split"], "train")
            self.assertEqual(replayed[0]["failure_attempts"], 1)
            self.assertEqual([t["id"] for t in replayed[-2:]], ["audit_holdout", "audit_holdout2"])
            cached = replay_tasks(replayed, config, state)
            self.assertEqual(len(cached), len(replayed))
            self.assertEqual(len({t["id"] for t in cached}), len(cached))
            self.assertEqual([t["id"] for t in cached[-2:]], ["audit_holdout", "audit_holdout2"])


if __name__ == "__main__":
    unittest.main()
