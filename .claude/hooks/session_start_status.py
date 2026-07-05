#!/usr/bin/env python3
"""SessionStart hook for AuroraIA-v2 multi-agent tracker.

Prints a compact aurora-status banner when Claude Code starts a session in
this repo. The banner reaches the user via the additionalContext field of the
hook output JSON.

Stays silent if the tracker is empty or unreadable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
TUNNEL_URL_FILE = REPO_ROOT / "tunnel_url.txt"


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

    leads = list((state.get("leads") or {}).keys())
    crosscut = state.get("crosscut") or []
    last = state.get("last_commit") or "—"
    goal = state.get("session_goal") or "—"

    tasks = state.get("tasks") or []
    in_flight = sum(1 for t in tasks if t.get("status") == "in_progress")
    done = sum(1 for t in tasks if t.get("status") == "done")
    blocked = sum(1 for t in tasks if t.get("status") == "blocked")

    # Surface the current tunnel URL so a fresh Claude session knows where
    # to probe + can tell the user. cloudflared --url generates a new
    # ephemeral hostname each restart; restart_tunnel.py writes it here.
    tunnel = "—"
    if TUNNEL_URL_FILE.exists():
        try:
            tunnel = TUNNEL_URL_FILE.read_text(encoding="utf-8").strip().splitlines()[0] or "—"
        except OSError:
            pass

    banner = (
        "Aurora agents ready — "
        f"{len(leads)} leads + {len(crosscut)} crosscut. "
        f"Last commit: {last}. "
        f"Tracker: {in_flight} in_flight, {done} done, {blocked} blocked. "
        f"Tunnel: {tunnel}. "
        f"Goal: {goal[:80]}"
    )

    output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": banner}}
    sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
