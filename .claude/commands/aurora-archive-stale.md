---
description: Auto-archive in_progress tracker tasks older than N minutes (dry-run by default)
allowed-tools: Bash
---

Preview which tasks would be archived (default 4h threshold):

```bash
python .claude/hooks/tracker_health.py --archive-after-min 240 --pretty
```

Apply the archival (mark stale `in_progress` tasks as `blocked` with verdict `auto-archived (stale Xh)`):

```bash
python .claude/hooks/tracker_health.py --archive-after-min 240 --apply --pretty
```

Custom threshold (e.g. archive anything older than 8h):

```bash
python .claude/hooks/tracker_health.py --archive-after-min 480 --apply
```

The watchdog (`/aurora-watchdog`) only **detects** stale work. This command **closes** it. Idempotent — running twice with the same threshold archives at most once per task. Atomic write — partial failures don't corrupt `state.json`.

Schema: `aurora.tracker_archive.v1`. Always dry-run unless `--apply` is passed.
