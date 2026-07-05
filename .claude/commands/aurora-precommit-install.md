---
description: Enable the portable Aurora pre-commit hook (lint + tests gate on agent system commits)
allowed-tools: Bash
---

Wire the project-tracked git hooks into git's hook resolution:

```bash
git config core.hooksPath .claude/git-hooks
```

After this, commits that touch `.claude/agents/`, `.claude/agent-tracker/`, `.claude/hooks/`, `.claude/git-hooks/`, or the route-test files automatically run:

1. `validate_agents.py` — frontmatter + tracker coherence + KNOWN_AGENTS sync
2. `test_hooks.py` — 15 unit tests on the 6 hooks
3. `test_route_test.py` — 13 routing tests (only when route-test files or threeDIntent.ts touched)

Total ~1.5 s when triggered. Zero overhead on commits that don't touch the agent system.

To disable: `git config --unset core.hooksPath`.
To bypass once: `git commit --no-verify` (not recommended).
