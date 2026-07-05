---
description: Run the Aurora hooks test suite (15 unit tests, stdlib-only)
allowed-tools: Bash
---

Run the unit tests for all 6 multi-agent hooks:

```bash
python .claude/hooks/test_hooks.py
```

Tests cover:

- `track_agent_dispatch.py` — Pre/Post round-trip, unknown agent filter, non-Task tool ignored, blocked-on-error, history rotation, malformed-payload fail-soft
- `record_last_commit.py` — git rev-parse + tracker write
- `session_start_status.py` — banner JSON + silent when tracker missing
- `precompact_tracker_summary.py` — summary with in-flight + done sections
- `prompt_routing_hint.py` — single/multi-lead detection + silent on no-match/empty
- `validate_agents.py` — real repo passes lint (37 agents coherent)

Each test runs in an isolated tmpdir so production tracker state is never touched. Total runtime ~0.7s.
