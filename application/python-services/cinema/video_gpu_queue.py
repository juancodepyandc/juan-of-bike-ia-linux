"""File GPU FIFO pour les travaux lourds du module video.

Le bridge conserve les processus et les resultats de jobs. Ce module ne gere
qu'une responsabilite : garantir qu'un seul job video detient le GPU, dans
l'ordre d'arrivee, tout en permettant d'annuler un job encore en attente.
Il ne depend ni de Flask ni de CUDA et se teste donc sans GPU.
"""

from __future__ import annotations

from collections import deque
import threading
import time
from typing import Callable


QueueUpdate = Callable[[int, str | None], None]


class VideoGpuQueue:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._pending: deque[str] = deque()
        self._active: str | None = None
        self._cancelled: set[str] = set()

    def enqueue(self, job_id: str) -> int:
        """Ajoute un job une seule fois et retourne sa position (1 = prochain)."""
        with self._condition:
            if job_id == self._active:
                return 0
            if job_id not in self._pending:
                self._pending.append(job_id)
                self._condition.notify_all()
            return list(self._pending).index(job_id) + 1

    def acquire(
        self,
        job_id: str,
        *,
        on_wait: QueueUpdate | None = None,
        poll_seconds: float = 0.25,
    ) -> bool:
        """Attend le tour du job. False signifie qu'il a ete annule en file."""
        self.enqueue(job_id)
        last_state: tuple[int, str | None] | None = None
        while True:
            with self._condition:
                if job_id in self._cancelled:
                    self._remove_pending(job_id)
                    self._condition.notify_all()
                    return False

                if self._active is None and self._pending and self._pending[0] == job_id:
                    self._pending.popleft()
                    self._active = job_id
                    self._condition.notify_all()
                    return True

                try:
                    position = list(self._pending).index(job_id) + 1
                except ValueError:
                    position = 0
                state = (position, self._active)
                self._condition.wait(timeout=max(0.01, poll_seconds))

            if on_wait is not None and state != last_state:
                on_wait(*state)
                last_state = state

    def release(self, job_id: str) -> None:
        with self._condition:
            if self._active == job_id:
                self._active = None
            self._cancelled.discard(job_id)
            self._condition.notify_all()

    def cancel(self, job_id: str) -> dict:
        """Marque un job annule et le retire de la file s'il n'est pas actif."""
        with self._condition:
            was_active = self._active == job_id
            was_pending = job_id in self._pending
            self._cancelled.add(job_id)
            if was_pending:
                self._remove_pending(job_id)
            self._condition.notify_all()
            return {
                "active": was_active,
                "queued": was_pending,
                "found": was_active or was_pending,
            }

    def is_cancelled(self, job_id: str) -> bool:
        with self._condition:
            return job_id in self._cancelled

    def snapshot(self, job_id: str | None = None) -> dict:
        with self._condition:
            pending = list(self._pending)
            position = None
            if job_id in pending:
                position = pending.index(job_id) + 1
            return {
                "active_job_id": self._active,
                "pending_job_ids": pending,
                "position": position,
            }

    def wait_until_idle(self, timeout: float) -> bool:
        """Helper de diagnostic/tests ; aucun appel de production ne bloque ici."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            while self._active is not None or self._pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True

    def _remove_pending(self, job_id: str) -> None:
        try:
            self._pending.remove(job_id)
        except ValueError:
            pass

