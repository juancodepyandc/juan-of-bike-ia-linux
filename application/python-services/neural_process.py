"""Keep long neural subprocesses observable without extending their deadline."""
from __future__ import annotations

import subprocess
import time


def run_neural_process(command, *, env=None, timeout=10800, heartbeat=30,
                       progress_stage="shape", progress_label="Calcul neuronal en cours"):
    started = time.monotonic()
    with subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as process:
        try:
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=min(heartbeat, remaining))
                    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= timeout:
                        raise
                    print(f"PROGRESS:{progress_stage}:{progress_label} ({int(time.monotonic() - started)} s)",
                          flush=True)
        except BaseException:
            process.kill()
            process.communicate()
            raise
