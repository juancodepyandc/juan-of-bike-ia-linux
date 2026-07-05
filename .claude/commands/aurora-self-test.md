---
description: Run all 7 gates of the Aurora multi-agent system in one shot (PASS/FAIL verdict)
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_selftest.py
```

Runs in ~3-4 s on a healthy system:

1. `validate_agents` — frontmatter + tracker + KNOWN_AGENTS coherence
2. `test_hooks` — 15 unit tests on the 6 hooks
3. `test_route_test` — 13 routing tests
4. `bridge_doctor --check-only` — bridge process + port + health
5. Bridge `GET /api/agents/list` — registry returns >=30 agents
6. Bridge `POST /api/3d/route-test` — Cat 1 fix verified live (dgPreferred=true)
7. `aurora_dashboard.py` — HTML rendering produces a non-empty file

Each gate runs independently — failures don't abort the run, you get the full report. Exit 0 if all green, 1 otherwise.

Use this:
- After a refactor that touches the agent system
- Before a release / merge to main
- When debugging "why is something broken" — narrows it down in seconds
