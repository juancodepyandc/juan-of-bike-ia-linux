---
description: Agent coverage report — declared vs dispatched (surfaces dead agents)
allowed-tools: Bash
---

```bash
python .claude/hooks/agent_coverage.py --pretty
```

JSON output (for piping):

```bash
python .claude/hooks/agent_coverage.py
```

Or via bridge endpoint:

```bash
curl -sS http://127.0.0.1:3001/api/agents/coverage | python -m json.tool
```

Walks every `.claude/agents/<name>.md` and counts dispatches per agent across `state.json` + `history/tasks-*.json`. The complement of `/aurora-metrics` (which only shows agents with ≥1 dispatch).

Surfaces the **dead set**: agents declared in the architecture but never actually used. A 5.3% coverage with 36 dead agents is normal for a young system; revisit periodically to either start using or retire dormant agents.

Schema: `aurora.coverage.v1`.
