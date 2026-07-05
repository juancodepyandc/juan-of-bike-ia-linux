# Aurora Agent Tracker

State and history of multi-agent dispatch for AuroraIA-v2.

## Files

- `state.json` — current dispatch state, written by `aurora-orchestrator` at every dispatch + completion. Schema: `aurora.tracker.v1`.
- `history/` — rolling archive, last 20 sessions.

## Schema (state.json)

```json
{
  "schema_version": "aurora.tracker.v1",
  "updated_at": "ISO8601",
  "session_goal": "human description of the current /loop iteration",
  "tasks": [
    {
      "id": "t1",
      "lead": "code-lead",
      "brief": "...",
      "status": "in_progress|done|blocked",
      "started_at": "ISO8601",
      "finished_at": "ISO8601|null",
      "verdict": "...|null",
      "files_touched": []
    }
  ],
  "tunnel_validated": false,
  "last_commit": "<sha>|null",
  "leads": { "<lead-name>": {"sub_agents": [...]} },
  "crosscut": ["tunnel-validator", "bridge-doctor"]
}
```

## Read with

```bash
cat .claude/agent-tracker/state.json | jq '.tasks[] | {id, lead, status, verdict}'
```

## Hierarchy

- **Master**: `aurora-orchestrator` — dispatches, never edits code
- **Leads** (7): one per AuroraIA module
- **Sub-agents** (9): focused workers under each lead
- **Crosscut** (2): `tunnel-validator` (E2E HTTP+UI), `bridge-doctor` (respawn diagnosis)

All agents pinned `model: claude-opus-4-7`. Run `python .claude/hooks/validate_agents.py` (or `/aurora-validate`) to verify tracker coherence with the agent files and the `KNOWN_AGENTS` allow-list in the dispatcher hook.
