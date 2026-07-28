"""Tests de concurrence CPU pour la file GPU video."""

from __future__ import annotations

import threading
import time
import unittest

from video_gpu_queue import VideoGpuQueue


class VideoGpuQueueTests(unittest.TestCase):
    def test_jobs_run_fifo_without_overlap(self):
        queue = VideoGpuQueue()
        events: list[str] = []
        first_has_gpu = threading.Event()
        let_first_finish = threading.Event()

        queue.enqueue("first")
        queue.enqueue("second")

        def first() -> None:
            self.assertTrue(queue.acquire("first"))
            events.append("first:start")
            first_has_gpu.set()
            let_first_finish.wait(timeout=2)
            events.append("first:end")
            queue.release("first")

        def second() -> None:
            self.assertTrue(queue.acquire("second"))
            events.append("second:start")
            queue.release("second")

        t1 = threading.Thread(target=first)
        t2 = threading.Thread(target=second)
        t1.start()
        t2.start()
        self.assertTrue(first_has_gpu.wait(timeout=1))
        time.sleep(0.05)
        self.assertEqual(events, ["first:start"])
        let_first_finish.set()
        t1.join(timeout=2)
        t2.join(timeout=2)

        self.assertEqual(
            events,
            ["first:start", "first:end", "second:start"],
        )
        self.assertTrue(queue.wait_until_idle(0.1))

    def test_queued_job_can_be_cancelled(self):
        queue = VideoGpuQueue()
        queue.enqueue("active")
        queue.enqueue("cancel-me")
        self.assertTrue(queue.acquire("active"))

        result: list[bool] = []
        waiter = threading.Thread(
            target=lambda: result.append(queue.acquire("cancel-me")),
        )
        waiter.start()
        time.sleep(0.05)
        verdict = queue.cancel("cancel-me")
        waiter.join(timeout=1)
        queue.release("active")

        self.assertTrue(verdict["queued"])
        self.assertEqual(result, [False])
        self.assertEqual(queue.snapshot()["pending_job_ids"], [])

    def test_enqueue_is_idempotent(self):
        queue = VideoGpuQueue()
        self.assertEqual(queue.enqueue("same"), 1)
        self.assertEqual(queue.enqueue("same"), 1)
        self.assertEqual(queue.snapshot()["pending_job_ids"], ["same"])


if __name__ == "__main__":
    unittest.main()
