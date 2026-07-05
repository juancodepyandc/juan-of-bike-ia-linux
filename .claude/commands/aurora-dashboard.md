---
description: Render a self-contained HTML dashboard from the agent tracker
allowed-tools: Bash
---

Render `.claude/agent-tracker/dashboard.html` from current state + history + agent files:

```bash
python .claude/hooks/aurora_dashboard.py
```

The script outputs the absolute path to the generated HTML file. Open it in any browser — no server, no JS frameworks, dark theme, monospace font, ~12 KB.

Shows:
- Header: schema, last_commit, session_goal
- Stats cards: agent count, leads, crosscut, total tasks, done/blocked/in-flight
- Leads grid: each lead as a card with sub-agents + delegate edges + description
- Recent tasks timeline: last 30 (current + history) with id, lead, status, brief, duration, verdict
