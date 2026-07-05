---
description: Query the bridge for the current agent registry (37 agents + 11 leads via /api/agents/list)
allowed-tools: Bash
---

```bash
curl -sS http://127.0.0.1:3001/api/agents/list | python -m json.tool
```

Returns: `{ok, schema_version, leads, crosscut, descriptions, agent_count}`.

For a single agent's full body: `curl http://127.0.0.1:3001/api/agents/<name>`.

Useful when integrating the agent registry into a UI panel, Chrome extension, or external dashboard. The data source is `.claude/agent-tracker/state.json` + `.claude/agents/*.md` frontmatter — same source the lint and dashboard use.
