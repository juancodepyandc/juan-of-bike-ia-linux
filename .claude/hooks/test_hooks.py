"""Unit tests for the AuroraIA-v2 multi-agent hooks.

Run from the repo root:

    python -m unittest .claude/hooks/test_hooks.py
    # or
    python .claude/hooks/test_hooks.py

Each hook is invoked as a subprocess with a tmpdir tracker so production
state.json is never touched. Tests are stdlib-only (no pytest) for portability
and CI simplicity.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / ".claude" / "hooks"


class HookTestBase(unittest.TestCase):
    """Each test gets its own tmpdir copy of the tracker so writes are isolated."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aurora-hooks-"))
        # Mirror just enough of the repo layout to resolve REPO_ROOT in hooks.
        (self.tmp / ".claude" / "agent-tracker").mkdir(parents=True)
        (self.tmp / ".claude" / "agents").mkdir(parents=True)
        (self.tmp / ".claude" / "hooks").mkdir(parents=True)
        # Copy hook scripts into the tmp tree so REPO_ROOT resolves there.
        for name in (
            "track_agent_dispatch.py",
            "record_last_commit.py",
            "session_start_status.py",
            "precompact_tracker_summary.py",
            "prompt_routing_hint.py",
            "validate_agents.py",
        ):
            shutil.copy2(HOOKS / name, self.tmp / ".claude" / "hooks" / name)
        self.tracker = self.tmp / ".claude" / "agent-tracker" / "state.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_hook(self, script: str, payload: dict) -> tuple[int, str, str]:
        """Invoke a hook with stdin = json.dumps(payload). Returns (rc, stdout, stderr)."""
        script_path = self.tmp / ".claude" / "hooks" / script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=10, check=False,
        )
        return result.returncode, result.stdout, result.stderr

    def read_tracker(self) -> dict:
        return json.loads(self.tracker.read_text(encoding="utf-8"))


class TrackAgentDispatchTests(HookTestBase):
    """Pre/PostToolUse pair on the Task tool."""

    def test_pre_post_pair_round_trip(self) -> None:
        rc, _, err = self.run_hook("track_agent_dispatch.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "tunnel-validator",
                "description": "smoke test",
                "prompt": "validate bridge"
            },
        })
        self.assertEqual(rc, 0, f"pre rc={rc} stderr={err}")
        state = self.read_tracker()
        self.assertEqual(len(state["tasks"]), 1)
        task = state["tasks"][0]
        self.assertEqual(task["lead"], "tunnel-validator")
        self.assertEqual(task["status"], "in_progress")

        rc, _, err = self.run_hook("track_agent_dispatch.py", {
            "hook_event_name": "PostToolUse",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "tunnel-validator", "description": "smoke test"},
            "tool_response": {"output": "OK"},
        })
        self.assertEqual(rc, 0, f"post rc={rc} stderr={err}")
        state = self.read_tracker()
        task = state["tasks"][0]
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["verdict"], "ok")
        self.assertIsNotNone(task["finished_at"])

    def test_unknown_agent_filtered(self) -> None:
        """general-purpose dispatches must NOT pollute the tracker."""
        rc, _, _ = self.run_hook("track_agent_dispatch.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "general-purpose", "description": "x"},
        })
        self.assertEqual(rc, 0)
        # Tracker file may not even exist yet (hook returned early).
        self.assertFalse(self.tracker.exists())

    def test_non_task_tool_ignored(self) -> None:
        rc, _, _ = self.run_hook("track_agent_dispatch.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        self.assertEqual(rc, 0)
        self.assertFalse(self.tracker.exists())

    def test_post_blocked_when_response_has_error(self) -> None:
        self.run_hook("track_agent_dispatch.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "code-lead", "description": "fix"},
        })
        self.run_hook("track_agent_dispatch.py", {
            "hook_event_name": "PostToolUse",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "code-lead", "description": "fix"},
            "tool_response": {"error": "tsc failed"},
        })
        task = self.read_tracker()["tasks"][0]
        self.assertEqual(task["status"], "blocked")
        self.assertIn("tsc failed", task["verdict"])

    def test_history_rotation_when_over_cap(self) -> None:
        """Push 60 done tasks via direct state write, then trigger one more — overflow archived."""
        state = {"schema_version": "aurora.tracker.v1", "tasks": []}
        for i in range(60):
            state["tasks"].append({
                "id": f"t{i}", "lead": "code-lead", "status": "done",
                "started_at": "2026-01-01T00:00:00Z",
                "finished_at": "2026-01-01T00:01:00Z",
                "verdict": "ok", "files_touched": [],
            })
        self.tracker.write_text(json.dumps(state), encoding="utf-8")

        # Trigger save by running another Pre/Post pair.
        self.run_hook("track_agent_dispatch.py", {
            "hook_event_name": "PreToolUse", "tool_name": "Task",
            "tool_input": {"subagent_type": "code-lead", "description": "x"},
        })
        new_state = self.read_tracker()
        self.assertLessEqual(len(new_state["tasks"]), 26,
                             "rotation should keep ~25 + the 1 new in-flight")
        history_dir = self.tmp / ".claude" / "agent-tracker" / "history"
        self.assertTrue(history_dir.is_dir())
        archives = list(history_dir.glob("tasks-*.json"))
        self.assertGreaterEqual(len(archives), 1, "history archive file should exist")

    def test_malformed_payload_is_fail_soft(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.tmp / ".claude" / "hooks" / "track_agent_dispatch.py")],
            input="this is not json", capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, "malformed stdin must not raise")


class RecordLastCommitTests(HookTestBase):

    def test_writes_sha_when_git_succeeds(self) -> None:
        # Need a working git repo for rev-parse. Reuse the real repo by symlinking
        # the tmp .git to the real one.
        real_git = REPO_ROOT / ".git"
        if not real_git.exists():
            self.skipTest("no .git in repo root")
        # Pre-seed tracker
        self.tracker.write_text(json.dumps({
            "schema_version": "aurora.tracker.v1", "tasks": [],
        }), encoding="utf-8")
        # The hook resolves REPO_ROOT relative to the *script's* location, which is
        # under tmp. Copy a .git directory pointer file so git -C works.
        os.symlink(real_git, self.tmp / ".git", target_is_directory=True)

        rc, _, err = self.run_hook("record_last_commit.py", {"hook_event_name": "Stop"})
        self.assertEqual(rc, 0, f"rc={rc} stderr={err}")
        state = self.read_tracker()
        self.assertIsNotNone(state.get("last_commit"))
        self.assertRegex(state["last_commit"], r"^[0-9a-f]{7}$")
        self.assertIsNotNone(state.get("last_commit_at"))


class SessionStartStatusTests(HookTestBase):

    def test_emits_banner_with_tracker_data(self) -> None:
        self.tracker.write_text(json.dumps({
            "schema_version": "aurora.tracker.v1",
            "leads": {"code-lead": {"sub_agents": []}},
            "crosscut": ["tunnel-validator"],
            "last_commit": "abc1234",
            "session_goal": "test session",
            "tasks": [
                {"id": "t1", "lead": "code-lead", "status": "in_progress"},
                {"id": "t2", "lead": "code-lead", "status": "done"},
            ],
        }), encoding="utf-8")
        rc, out, _ = self.run_hook("session_start_status.py",
                                   {"hook_event_name": "SessionStart", "source": "startup"})
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("abc1234", ctx)
        self.assertIn("1 in_flight", ctx)
        self.assertIn("1 done", ctx)
        self.assertIn("test session", ctx)

    def test_silent_when_tracker_missing(self) -> None:
        rc, out, _ = self.run_hook("session_start_status.py",
                                   {"hook_event_name": "SessionStart"})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")


class PrecompactTrackerSummaryTests(HookTestBase):

    def test_emits_summary_with_inflight_and_done(self) -> None:
        self.tracker.write_text(json.dumps({
            "schema_version": "aurora.tracker.v1",
            "last_commit": "deadbee",
            "session_goal": "tour 7",
            "tasks": [
                {"id": "ta", "lead": "code-lead", "brief": "b1", "status": "in_progress"},
                {"id": "tb", "lead": "3d-lead", "brief": "b2", "status": "done", "verdict": "ok"},
            ],
        }), encoding="utf-8")
        rc, out, _ = self.run_hook("precompact_tracker_summary.py",
                                   {"hook_event_name": "PreCompact", "trigger": "manual"})
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("deadbee", ctx)
        self.assertIn("In-flight", ctx)
        self.assertIn("Recent done", ctx)
        self.assertIn("code-lead", ctx)


class PromptRoutingHintTests(HookTestBase):

    def test_single_lead_match(self) -> None:
        rc, out, _ = self.run_hook("prompt_routing_hint.py", {
            "prompt": "voxtral STT crash quand kokoro charge en parallèle",
        })
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("voice-lead", ctx)

    def test_multi_lead_match(self) -> None:
        rc, out, _ = self.run_hook("prompt_routing_hint.py", {
            "prompt": "le motion preset I2V crash et le motion_baker non plus",
        })
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("multiple modules", ctx)
        self.assertIn("aurora-orchestrator", ctx)

    def test_silent_on_no_match(self) -> None:
        rc, out, _ = self.run_hook("prompt_routing_hint.py", {"prompt": "how is the weather"})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_silent_on_empty_prompt(self) -> None:
        rc, out, _ = self.run_hook("prompt_routing_hint.py", {})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")


class ValidateAgentsTests(HookTestBase):
    """validate_agents.py runs against the real .claude/agents/ — verify it stays green."""

    def test_real_repo_passes_lint(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / ".claude" / "hooks" / "validate_agents.py")],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0,
                         f"lint must be green; stderr={result.stderr}")
        self.assertIn("OK", result.stdout)

    def test_env_check_aurora_scripts_pass(self) -> None:
        """check_aurora_scripts must report PASS on the real repo —
        every core script in the v80 attribution chain is present."""
        sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))
        try:
            from aurora_env_check import check_aurora_scripts  # type: ignore
        finally:
            try:
                sys.path.remove(str(REPO_ROOT / ".claude" / "hooks"))
            except ValueError:
                pass
        c = check_aurora_scripts()
        self.assertEqual(c.level, "PASS",
                         f"aurora_scripts must pass on real repo; detail={c.detail}")
        self.assertIn("core scripts", c.detail)

    def test_catches_broken_slash_script_reference(self) -> None:
        """The slash-command linter must reject a command that references
        a non-existent script. Locks the script-resolution check in CI."""
        broken = REPO_ROOT / ".claude" / "commands" / "_test_broken.md"
        broken.write_text(
            "---\ndescription: broken test slash\nallowed-tools: Bash\n---\n\n"
            "```bash\npython .claude/hooks/this_does_not_exist.py\n```\n",
            encoding="utf-8",
        )
        try:
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / ".claude" / "hooks" / "validate_agents.py")],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10, check=False,
            )
            self.assertEqual(result.returncode, 1,
                             f"linter must FAIL on dangling script ref; stdout={result.stdout}")
            self.assertIn("non-existent script", result.stderr)
            self.assertIn("_test_broken.md", result.stderr)
        finally:
            broken.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
