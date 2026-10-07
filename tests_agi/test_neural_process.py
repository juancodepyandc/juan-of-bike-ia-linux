"""Real short-lived child processes; no GPU or neural weights."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location('neural_process',
    Path(__file__).resolve().parents[1] / 'application/python-services/neural_process.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def test_long_child_keeps_output_exit_status_and_stage_progress():
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = runtime.run_neural_process([sys.executable, '-c',
            "import sys,time; print('retained stdout'); print('retained stderr',file=sys.stderr); time.sleep(.15); sys.exit(7)"],
            timeout=5, heartbeat=.05, progress_stage='geometrie', progress_label='Repair running')
    assert result.returncode == 7
    assert result.stdout.strip() == 'retained stdout'
    assert result.stderr.strip() == 'retained stderr'
    assert 'PROGRESS:geometrie:Repair running' in output.getvalue()


def test_heartbeats_do_not_extend_the_child_deadline():
    import pytest
    started = time.monotonic()
    with contextlib.redirect_stdout(io.StringIO()), pytest.raises(subprocess.TimeoutExpired):
        runtime.run_neural_process([sys.executable, '-c', 'import time; time.sleep(30)'],
                                   timeout=.3, heartbeat=.05)
    assert time.monotonic() - started < 5
