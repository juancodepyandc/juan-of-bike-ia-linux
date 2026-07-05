---
description: Pre-ship verification — run all gates + check tree clean + check pushed (single GO/BLOCK verdict)
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_shipit.py
```

Runs in order:
1. **`self_test_17_gates`** — full `/aurora-self-test` (lint, hook tests, route tests, 8 bridge endpoints, metrics, changelog, dashboard)
2. **`typescript_meshRescue`** — Node `--test` on the TS bridge client (13 tests)
3. **`git_tree_clean`** — only session artifacts allowed dirty; any code change blocks
4. **`head_pushed_to_origin`** — `git fetch origin main` + `merge-base --is-ancestor HEAD origin/main` proves the local HEAD is reachable from origin

Exit `0` GO when all green, `1` BLOCK with the failing gate listed.

Use it before:
- closing a working session
- handing off to another contributor / agent
- running `update-aurora.bat` (which `git reset --hard` — must be pushed first)

Live verdict format:
```
[aurora-ship-it] running pre-ship gates...
  [ok ] self_test_17_gates           [aurora-self-test] PASS — all 17 gates green.
  [ok ] typescript_meshRescue        ✔ rescueMeshAutonomous helper (...)
  [ok ] git_tree_clean               no code changes (only session artifacts allowed)
  [ok ] head_pushed_to_origin        HEAD 7a2ca1c on origin/main

[aurora-ship-it] GO — all 4 pre-ship gates green.
```
