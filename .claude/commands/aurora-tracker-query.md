---
description: Query tracker dispatches by run_id / lead / status / since (closes the audit chain)
allowed-tools: Bash
---

Show every dispatch that touched a given run_id (pipeline + every rescue stage):

```bash
python .claude/hooks/tracker_query.py --run-id cat5_jellopus_mesh --pretty
```

Find all blocked dispatches under a specific lead since a date:

```bash
python .claude/hooks/tracker_query.py --lead 3d-quality-rescuer --status blocked --since 2026-04-30T00:00:00Z --pretty
```

JSON output (for piping):

```bash
python .claude/hooks/tracker_query.py --run-id cat5 --limit 20
```

Or via bridge endpoint:

```bash
curl -sS "http://127.0.0.1:3001/api/agents/dispatches?run_id=cat5_jellopus_mesh&limit=10" | python -m json.tool
```

Walks `state.json` + `history/tasks-*.json`, applies AND-semantics across filters, returns newest-first.

The `--run-id` filter matches both `metadata.run_id` (set by `tracker_helper`) **and** any occurrence in `brief` (catches older entries that pre-date the metadata field).

Schema: `aurora.tracker_query.v1`.
