#!/usr/bin/env python3
"""Stop hook for AuroraIA-v2 multi-agent tracker.

Runs when Claude Code finishes a turn (Stop event). Records the current HEAD
SHA to the tracker so we know which commit closed the session. Idempotent and
fail-soft.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"


def warn(msg: str) -> None:
    sys.stderr.write(f"[record-commit] {msg}\n")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def head_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=7", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        warn(f"git rev-parse failed: {exc}")
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def main() -> int:
    try:
        json.load(sys.stdin)  # consume payload, we don't need fields
    except json.JSONDecodeError:
        pass

    sha = head_sha()
    if sha is None:
        return 0

    if not TRACKER.exists():
        return 0

    try:
        state = json.loads(TRACKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warn(f"could not read state.json ({exc})")
        return 0

    if state.get("last_commit") == sha:
        return 0

    state["last_commit"] = sha
    state["last_commit_at"] = now_iso()
    state["updated_at"] = now_iso()

    try:
        tmp = TRACKER.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, TRACKER)
    except OSError as exc:
        warn(f"could not write state.json ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
