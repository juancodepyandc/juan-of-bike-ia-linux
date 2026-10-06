"""Exercise isolated launcher functions; never execute the publishing script."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "start-aurora.sh").read_text(encoding="utf-8")


def shell_function(name):
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}", SOURCE, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"Missing launcher function {name}")
    return match.group(0)


FIXTURE_PYTHON = """#!/usr/bin/env python3
import io, json, os, pathlib, sys, types, urllib.request
if sys.argv[1] != '-':
    with open(os.environ['FIXTURE_LAUNCH_LOG'], 'a') as output:
        output.write(sys.argv[1] + '\\n')
    sys.exit(int(os.environ.get('FIXTURE_CHILD_EXIT', '1')))
code = sys.stdin.read()
payload = os.environ.get('FIXTURE_HTTP_BODY', '{}')
class Response(io.StringIO):
    pass
urllib.request.urlopen = lambda *args, **kwargs: Response(payload)
def probe_sync(**kwargs):
    state_path = pathlib.Path(os.environ['FIXTURE_BUS_COUNTER'])
    count = int(state_path.read_text()) if state_path.exists() else 0
    state_path.write_text(str(count + 1))
    states = json.loads(os.environ.get('FIXTURE_BUS_STATES', '[false]'))
    return {'ok': states[min(count, len(states) - 1)]}
bus = types.ModuleType('agi_core.bus')
bus.probe_sync = probe_sync
sys.modules['agi_core'] = types.ModuleType('agi_core')
sys.modules['agi_core.bus'] = bus
exec(compile(code, '<launcher-probe>', 'exec'))
"""


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Linux/macOS launcher requires POSIX Bash')
class LauncherReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.python = self.directory / "fixture-python"
        self.python.write_text(FIXTURE_PYTHON, encoding="utf-8")
        self.python.chmod(0o755)
        self.launch_log = self.directory / "launches.log"
        self.sleep_log = self.directory / "sleep.log"
        self.env = dict(os.environ, APP_PY=str(self.python), ROOT_DIR=str(self.directory),
            APP_DIR=str(self.directory), LOG_DIR=str(self.directory),
            FIXTURE_LAUNCH_LOG=str(self.launch_log), FIXTURE_SLEEP_LOG=str(self.sleep_log),
            FIXTURE_BUS_COUNTER=str(self.directory / "bus-counter"))

    def run_functions(self, body, *, http=None, bus=None, child_exit=1):
        env = dict(self.env, FIXTURE_HTTP_BODY=json.dumps(http),
                   FIXTURE_BUS_STATES=json.dumps(bus or [False]), FIXTURE_CHILD_EXIT=str(child_exit))
        functions = "\n".join(shell_function(name) for name in
                              ("bridge_is_running", "daemon_is_running", "run_agi_supervisor"))
        script = "set -euo pipefail\n" + functions + "\n" + textwrap.dedent("""
            sleep() { printf 'sleep\\n' >> "$FIXTURE_SLEEP_LOG"; }
        """) + "\n" + body
        return subprocess.run(["bash", "-c", script], env=env, capture_output=True,
                              text=True, timeout=10)

    def launches(self):
        return self.launch_log.read_text().splitlines() if self.launch_log.exists() else []

    def test_bridge_requires_aurora_protocol_json(self):
        for payload, expected in (({"ok": True, "service": "aurora-bridge"}, True),
                                  ({"ok": True, "service": "foreign-server"}, False),
                                  ({"ok": "true", "service": "aurora-bridge"}, False),
                                  ({"ok": False, "service": "aurora-bridge"}, False),
                                  (["ok"], False)):
            with self.subTest(payload=payload):
                result = self.run_functions("if bridge_is_running; then exit 0; else exit 1; fi", http=payload)
                self.assertEqual(result.returncode == 0, expected, result.stderr)
        self.assertEqual(self.launches(), [])

    def test_daemon_checks_bus_protocol_probe_boolean(self):
        for state, expected in ((True, True), (False, False), ("true", False)):
            with self.subTest(state=state):
                result = self.run_functions("if daemon_is_running; then exit 0; else exit 1; fi", bus=[state])
                self.assertEqual(result.returncode == 0, expected, result.stderr)
        self.assertEqual(self.launches(), [])

    def test_existing_daemon_stops_supervisor_without_launching(self):
        result = self.run_functions("run_agi_supervisor", bus=[True])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.launches(), [])
        self.assertFalse(self.sleep_log.exists())

    def test_daemon_arriving_after_child_exit_prevents_restart(self):
        result = self.run_functions("run_agi_supervisor", bus=[False, True])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.launches(), ["aurora_agi_daemon.py"])
        self.assertFalse(self.sleep_log.exists())
        self.assertIn("aucun redémarrage", (self.directory / "agi_daemon.log").read_text())

    def test_daemon_arriving_during_backoff_prevents_next_launch(self):
        result = self.run_functions("run_agi_supervisor", bus=[False, False, True])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.launches(), ["aurora_agi_daemon.py"])
        self.assertEqual(self.sleep_log.read_text().splitlines(), ["sleep"])

    def test_clean_child_exit_does_not_restart(self):
        result = self.run_functions("run_agi_supervisor", bus=[False], child_exit=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.launches(), ["aurora_agi_daemon.py"])
        self.assertFalse(self.sleep_log.exists())

    def test_start_fragment_reuses_running_bridge_and_daemon(self):
        fragment = SOURCE.split('echo "[3/5] Bridge Python"', 1)[1].split('echo "[4/5]', 1)[0]
        result = self.run_functions(fragment + "\nwait", http={"ok": True, "service": "aurora-bridge"}, bus=[True])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.launches(), [])
        self.assertIn("Bridge existant réutilisé", result.stdout)
        self.assertIn("Démon AGI existant réutilisé", result.stdout)


if __name__ == "__main__":
    unittest.main()
