---
description: Regenerate HANDOFF.md — single-page situational awareness for the next session
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_handoff.py
```

Or print to stdout without writing:

```bash
python .claude/hooks/aurora_handoff.py --stdout
```

Pulls together:
- HEAD branch + SHA + last subject + date + `pushed to origin/main` flag
- `/aurora-self-test` snapshot (verdict + per-gate output)
- Agent tracker state (schema, last_commit, session_goal, in-flight / done / blocked)
- 3D run index (grouped runs, standalones, rescued meshes)
- Last 12 commits with v-tagged headlines
- Useful command cheatsheet
- "What's reliably true today" facts (38 agents, 102 tests, etc.)

Writes to `HANDOFF.md` at repo root. Idempotent. Reads stay current via:
- `git log` / `git rev-parse` for HEAD info
- `aurora_selftest.py` subprocess for the snapshot
- `state.json` direct read for tracker
- `mesh_run_index.index_runs()` for 3D inventory

Run before:
- ending a long working session
- handing off to another contributor
- running `/loop` for the night so the next firing knows where it stands

The output is committed-friendly — `HANDOFF.md` is the artifact a new
contributor reads first.
