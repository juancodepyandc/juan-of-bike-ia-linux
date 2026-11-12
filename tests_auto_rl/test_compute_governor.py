import unittest
from unittest.mock import patch

from auto_rl.compute_governor import plan_compute, worker_capacity


class ComputeGovernor(unittest.TestCase):
    def worker(self, size=16):
        return {"last_heartbeat": 1000, "status": "ready", "device_free_vram_gb": [size],
                "available_ram_gb": 40, "remaining_seconds": 3600}

    def requirements(self, size=8):
        return {"vram_per_device_gb": size, "ram_gb": 10, "duration_seconds": 600, "checkpoint_seconds": 60}

    def test_does_not_sum_two_gpus(self):
        worker = {**self.worker(), "device_free_vram_gb": [16, 16]}
        plan = plan_compute(self.requirements(24), {"kaggle": worker}, now=1000)
        self.assertIsNone(plan["selected_worker"])
        self.assertIn("insufficient_per_device_vram", plan["decisions"][0]["reasons"])

    def test_best_fit_preserves_large_gpu_for_large_jobs(self):
        workers = {"colab": self.worker(96), "kaggle": self.worker(16)}
        self.assertEqual(plan_compute(self.requirements(), workers, now=1000)["selected_worker"], "kaggle")
        self.assertEqual(plan_compute(self.requirements(60), workers, now=1000)["selected_worker"], "colab")

    def test_stale_busy_unknown_capacity_and_checkpoint_budget_block(self):
        for delta in ({"last_heartbeat": 0}, {"status": "training:code"},
                      {"available_ram_gb": None}, {"device_free_vram_gb": None},
                      {"remaining_seconds": 630}, {"remaining_seconds": None},
                      {"last_heartbeat": 1001}, {"device_free_vram_gb": [float("nan")]}):
            with self.subTest(delta=delta):
                result = plan_compute(self.requirements(), {"worker": {**self.worker(), **delta}}, now=1000)
                self.assertIsNone(result["selected_worker"])
                self.assertFalse(result["dispatched"])

    def test_missing_or_invalid_requirements_rejected(self):
        for delta in ({"ram_gb": True}, {"ram_gb": float("nan")}, {"device_count": 2}):
            with self.assertRaises(ValueError):
                plan_compute({**self.requirements(), **delta}, {}, now=1000)

    def test_heartbeat_cannot_extend_a_fixed_session_deadline(self):
        worker = {**self.worker(), "session_deadline": 1500, "last_heartbeat": 1100}
        self.assertEqual(worker_capacity(worker, now=1100)["remaining_seconds"], 400)
        self.assertIsNone(plan_compute(self.requirements(), {"worker": worker}, now=1100)["selected_worker"])

    def test_colab_status_does_not_count_stale_worker_or_invent_gpu(self):
        from auto_rl import colab_live_bridge as bridge
        with patch.object(bridge, "read_json", return_value={"workers": {"old": self.worker()}}), patch.object(bridge.time, "time", return_value=2000):
            status = bridge.get_colab_bridge_status()
        self.assertFalse(status["active"])
        self.assertEqual(status["connected_workers_count"], 0)
        self.assertEqual(status["stale_workers_count"], 1)
        with patch.object(bridge, "read_json", return_value={}), patch.object(bridge, "atomic_json") as write:
            bridge.register_colab_worker({"worker_id": "unknown"})
            worker = write.call_args.args[1]["workers"]["unknown"]
            self.assertIsNone(worker["gpu_name"])
            self.assertIsNone(worker["vram_gb"])
            self.assertFalse(worker["fp8_supported"])
