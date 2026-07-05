#!/usr/bin/env python3
"""PreCompact hook for AuroraIA-v2 multi-agent tracker.

Fires just before Claude Code compacts the conversation context. Injects a
compact summary of the tracker (last_commit, in-flight tasks, recent dones)
into the additionalContext channel so the post-compact session retains
situational awareness about which leads were dispatched.

Stays silent if the tracker is empty.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"


def main() -> int:
    try:
        json.load(sys.stdin)  # payload not needed
    except json.JSONDecodeError:
        pass

    if not TRACKER.exists():
        return 0
    try:
        state = json.loads(TRACKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    tasks = state.get("tasks") or []
    in_flight = [t for t in tasks if t.get("status") == "in_progress"]
    recent_done = [t for t in tasks if t.get("status") == "done"][-5:]
    recent_blocked = [t for t in tasks if t.get("status") == "blocked"][-3:]

    last_commit = state.get("last_commit") or "—"
    goal = state.get("session_goal") or "—"

    lines = [
        f"AuroraIA agent tracker — last_commit {last_commit}, goal: {goal[:120]}",
    ]
    if in_flight:
        lines.append(f"In-flight ({len(in_flight)}):")
        for t in in_flight[-5:]:
            lines.append(f"  - [{t.get('id','?')}] {t.get('lead','?')} — {(t.get('brief') or '')[:80]}")
    if recent_done:
        lines.append(f"Recent done ({len(recent_done)}):")
        for t in recent_done:
            lines.append(f"  - [{t.get('id','?')}] {t.get('lead','?')} — {(t.get('verdict') or 'ok')[:60]}")
    if recent_blocked:
        lines.append(f"Recent blocked ({len(recent_blocked)}):")
        for t in recent_blocked:
            lines.append(f"  - [{t.get('id','?')}] {t.get('lead','?')} — {(t.get('verdict') or '?')[:60]}")

    summary = "\n".join(lines)
    output = {"hookSpecificOutput": {"hookEventName": "PreCompact", "additionalContext": summary}}
    sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
