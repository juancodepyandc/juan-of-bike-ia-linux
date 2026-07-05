---
description: Print current state of the Aurora agent tracker (in-flight, done, blocked tasks)
allowed-tools: Read, Bash
---

Read `.claude/agent-tracker/state.json` and print a compact human-readable status:

- session_goal
- tasks: id | lead | status | verdict (truncated)
- tunnel_validated
- last_commit

If history exists, show the last 3 archived sessions from `.claude/agent-tracker/history/`.
