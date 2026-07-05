---
description: Print per-lead dispatch metrics derived from the tracker
allowed-tools: Bash
---

```bash
python .claude/hooks/agent_metrics.py --pretty
```

JSON output (for piping):

```bash
python .claude/hooks/agent_metrics.py
```

Or via bridge endpoint (HTTP):

```bash
curl -sS http://127.0.0.1:3001/api/agents/metrics | python -m json.tool
```

Aggregates `state.json` + `history/tasks-*.json`:

- per-lead: count, done, blocked, in-progress, avg/min/max duration (s), last finished_at + status + verdict
- global: total dispatches, done, blocked, success rate

Schema: `aurora.metrics.v1`. Used by the dashboard, the self-test, and external observability tooling.
