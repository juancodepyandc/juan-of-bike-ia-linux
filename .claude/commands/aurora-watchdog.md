---
description: Consolidated ops view — tracker health + recent dispatches + rescue trend + top runs
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_watchdog.py --pretty
```

Tune the surface:

```bash
python .claude/hooks/aurora_watchdog.py --pretty --stale-min 60 --recent 8 --top 5
```

JSON output (for piping):

```bash
python .claude/hooks/aurora_watchdog.py
```

Bundles four read-only probes into one terminal screen:

1. **Tracker health** — `in_progress` / stale tasks (older than `--stale-min`)
2. **Recent dispatches** — last `--recent` entries with status, lead, verdict
3. **Rescue trend** — promote rate, mean delta, axis lifts
4. **Top runs** — best `--top` runs by final score with progression

All read-only, ~200ms total. The dashboard remains the durable visual; this is the CLI summary for shells & tunnels.

Schema: `aurora.watchdog.v1`.
